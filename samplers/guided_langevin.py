import json
import logging

import cv2
import torchvision.transforms as transforms
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from skimage.metrics import peak_signal_noise_ratio as psnr
from skimage.metrics import structural_similarity as ssim

from datasets import get_dataloader
from datasets.utils import *
from models import get_sigmas
from models.ncsnv2 import NCSNv2Deepest
from utils import get_all_files

__all__ = ['guided_LD']


class guided_LD:
    def __init__(self, args, config):
        self.args = args
        self.config = config
        self.device = config.device
        self.files = get_all_files(config.data_dir, pattern='*.h5')
        self.transform = transforms.Compose([transforms.ToTensor()])

        self.ssim_scores = []
        self.psnr_scores = []

        os.makedirs(args.log_path, exist_ok=True)

    @torch.no_grad()
    def sample(self):

        # load model
        score = NCSNv2Deepest(self.config).to(self.device)
        score = torch.nn.DataParallel(score)
        states = torch.load(self.config.model_path)
        score.load_state_dict(states[0], strict=True)

        # get dataset
        dataloader = get_dataloader(self.files, self.config, self.args)

        # configure diffusion
        sigmas_torch = get_sigmas(self.config).to(self.device)
        sigmas = sigmas_torch.cpu().numpy()

        # guided Langevin Dynamics
        timesteps = self.config.model.num_classes - self.config.sampling.start_iter + 1
        log_interval = 1 if timesteps < 5 else timesteps // 5
        logging.info(f'Total batches {len(dataloader)}')
        for idx, X in enumerate(dataloader):

            ref, mvue, maps, mask = X['ground_truth'], X['mvue'], X['maps'], X['mask']
            ref = ref.to(self.device).type(torch.complex128)
            mvue = mvue.to(self.device)
            maps = maps.to(self.device)
            mask = mask.to(self.device)
            estimated_mvue = torch.tensor(get_mvue(ref.cpu().numpy(), maps.cpu().numpy()), device=self.device)
            forward_operator = lambda x: MulticoilForwardMRI(self.args.orientation)(
                torch.complex(x[:, 0], x[:, 1]),
                maps, mask)

            xt = torch.randn((self.config.batch_size, 2, self.config.image_size[0], self.config.image_size[1]),
                             device=self.device)

            for step in range(self.config.model.num_classes):
                if step <= self.config.sampling.start_iter:
                    continue
                if step <= 1800:
                    n_steps_each = 3
                else:
                    n_steps_each = self.config.sampling.n_steps_each

                if step % log_interval == 0:
                    logging.info(f'Batch: {idx} - Step: {step}')

                sigma = sigmas[step]
                labels = (torch.ones(xt.shape[0], device=xt.device) * step).long()
                step_size = self.config.sampling.step_lr * (sigma / sigmas[-1]) ** 2

                for _ in range(n_steps_each):
                    noise = torch.randn_like(xt) * np.sqrt(step_size * 2)
                    p_grad = score(xt, labels)

                    meas = forward_operator(normalize(xt, estimated_mvue))
                    meas_grad = torch.view_as_real(
                        torch.sum(ifft(meas - ref) * torch.conj(maps), axis=1)).permute(0, 3, 1, 2)
                    meas_grad = unnormalize(meas_grad, estimated_mvue)
                    meas_grad = meas_grad.type(torch.cuda.FloatTensor)
                    meas_grad /= torch.norm(meas_grad)
                    meas_grad *= torch.norm(p_grad)
                    meas_grad *= self.config.sampling.mse

                    xt = xt + step_size * (p_grad - meas_grad) + noise

            xt = normalize(xt, estimated_mvue)
            to_display = torch.view_as_complex(
                xt.permute(0, 2, 3, 1).reshape(-1, self.config.image_size[0], self.config.image_size[1],
                                               2).contiguous()).abs()
            to_display = to_display.flip(-2)

            for i in range(self.config.batch_size):

                recon_img = to_display[i].unsqueeze(dim=0)
                orig_img = mvue[i].abs().flip(-2)

                orig_th, recon_th, orig_np, recon_np = self.edit(self.config, orig_img, recon_img)
                ssim_score = ssim(orig_np, recon_np)
                psnr_score = psnr(orig_np, recon_np)
                self.ssim_scores.append(ssim_score)
                self.psnr_scores.append(psnr_score)

                if self.args.save_images:
                    slice_idx = X["slice_idx"][i].item()
                    file_name = os.path.join(self.args.log_path, f'{self.config.anatomy}_{slice_idx}_or.jpg')
                    save_images(orig_th, file_name, normalize=True)

                    recon_np = Image.fromarray(recon_np)
                    draw = ImageDraw.Draw(recon_np)
                    font = ImageFont.truetype(
                        '/content/image_processing_with_python/09_drawing_text/Gidole-Regular.ttf', 16
                    )
                    draw.text((175, 360), "SSIM: {:0.2f}".format(ssim_score), 255, font=font)
                    draw.text((265, 360), "PSNR: {:0.2f}(db)".format(psnr_score), 255, font=font)
                    file_name = os.path.join(self.args.log_path, f'{self.config.anatomy}_{slice_idx}.jpg')
                    recon_np.save(file_name)

        stats_dict = {'ssim': self.ssim_scores, 'psnr': self.psnr_scores}
        stats_file = os.path.join(self.args.log_path, 'stats.json')
        with open(stats_file, 'w') as f:
            json.dump(stats_dict, f, indent=2)

    def edit(self, config, orig_img, recon_img):

        if config.denoise_005:
            recon_img[recon_img <= 0.05 * torch.max(orig_img)] = 0
            orig_img[orig_img <= 0.05 * torch.max(orig_img)] = 0

        orig_np = orig_img.squeeze().cpu().numpy()
        orig_np *= 255.0 / orig_np.max()
        orig_np = orig_np.astype(np.uint8)
        recon_np = recon_img.squeeze().cpu().numpy()
        recon_np *= 255.0 / recon_np.max()
        recon_np = recon_np.astype(np.uint8)

        if config.circle_mask:
            mask = np.zeros(recon_np.shape, dtype=np.uint8)
            cv2.circle(mask, (192, 192), 165, 255, -1)
            recon_np = cv2.bitwise_and(recon_np, recon_np, mask=mask)

        return orig_img, recon_img, orig_np, recon_np
