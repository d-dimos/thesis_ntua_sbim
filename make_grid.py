import argparse
import os
import sys

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torchvision import transforms
from torchvision.io import read_image, ImageReadMode
from torchvision.utils import make_grid


def edit(orig_img, recon_img):
    recon_img[recon_img <= 0.05 * torch.max(orig_img)] = 0
    orig_img[orig_img <= 0.05 * torch.max(orig_img)] = 0

    orig_np = orig_img.squeeze().cpu().numpy()
    recon_np = recon_img.squeeze().cpu().numpy()

    mask = np.zeros(recon_np.shape, dtype=np.uint8)
    cv2.circle(mask, (192, 192), 165, 255, -1)
    recon_np = cv2.bitwise_and(recon_np, recon_np, mask=mask)

    return orig_img, recon_img, orig_np, recon_np


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exp_dir', type=str, required=True, help='Path to experiment images')
    args = parser.parse_args()
    return args


def main():
    args = get_args()

    to_plot = []
    for i in range(4):
        origi = read_image(os.path.join(args.exp_dir, f'brain_T2_{i}_or.jpg'), mode=ImageReadMode.GRAY)
        recon = read_image(os.path.join(args.exp_dir, f'brain_T2_{i}.jpg'))

        _, _, orig_np, recon_np = edit(origi, recon)

        pad = (1,1,1,1)
        origi = F.pad(origi, pad, "constant", 255)
        recon = F.pad(recon, pad, "constant", 255)

        to_plot.append(origi)
        to_plot.append(recon)

    grid = make_grid(to_plot, nrow=2, ncol=4, padding=0)
    grid = transforms.ToPILImage()(grid)
    grid.save(os.path.join(args.exp_dir, f'brains_grid0.jpg'))

    to_plot = []
    for i in range(4,8):
        origi = read_image(os.path.join(args.exp_dir, f'brain_T2_{i}_or.jpg'), mode=ImageReadMode.GRAY)
        recon = read_image(os.path.join(args.exp_dir, f'brain_T2_{i}.jpg'))

        _, _, orig_np, recon_np = edit(origi, recon)

        pad = (1,1,1,1)
        origi = F.pad(origi, pad, "constant", 255)
        recon = F.pad(recon, pad, "constant", 255)

        to_plot.append(origi)
        to_plot.append(recon)

    grid = make_grid(to_plot, nrow=2, ncol=4, padding=0)
    grid = transforms.ToPILImage()(grid)
    grid.save(os.path.join(args.exp_dir, f'brains_grid1.jpg'))

    to_plot = []
    for i in range(8, 12):
        origi = read_image(os.path.join(args.exp_dir, f'brain_T2_{i}_or.jpg'), mode=ImageReadMode.GRAY)
        recon = read_image(os.path.join(args.exp_dir, f'brain_T2_{i}.jpg'))

        _, _, orig_np, recon_np = edit(origi, recon)

        pad = (1,1,1,1)
        origi = F.pad(origi, pad, "constant", 255)
        recon = F.pad(recon, pad, "constant", 255)

        to_plot.append(origi)
        to_plot.append(recon)

    grid = make_grid(to_plot, nrow=2, ncol=4, padding=0)
    grid = transforms.ToPILImage()(grid)
    grid.save(os.path.join(args.exp_dir, f'brains_grid2.jpg'))

    to_plot = []
    for i in range(12, 16):
        origi = read_image(os.path.join(args.exp_dir, f'brain_T2_{i}_or.jpg'), mode=ImageReadMode.GRAY)
        recon = read_image(os.path.join(args.exp_dir, f'brain_T2_{i}.jpg'))

        _, _, orig_np, recon_np = edit(origi, recon)

        pad = (1,1,1,1)
        origi = F.pad(origi, pad, "constant", 255)
        recon = F.pad(recon, pad, "constant", 255)

        to_plot.append(origi)
        to_plot.append(recon)

    grid = make_grid(to_plot, nrow=2, ncol=4, padding=0)
    grid = transforms.ToPILImage()(grid)
    grid.save(os.path.join(args.exp_dir, f'brains_grid3.jpg'))

    return 0


if __name__ == '__main__':
    sys.exit(main())