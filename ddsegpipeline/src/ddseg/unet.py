from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np
import torch
from torch import nn


@dataclass(frozen=True)
class UNetConfig:
    input_channels: int = 5
    num_classes: int = 4
    dropout_prob: float = 0.5


class MatlabUNet(nn.Module):
    def __init__(self, mean: np.ndarray, cfg: UNetConfig = UNetConfig()) -> None:
        super().__init__()
        if mean.ndim != 3:
            raise ValueError(f"Expected mean shape (H,W,C), got {mean.shape}")

        # Store mean as NCHW for broadcast subtraction.
        mean_nchw = torch.from_numpy(mean.transpose(2, 0, 1)).float().unsqueeze(0)
        self.register_buffer("mean", mean_nchw, persistent=False)

        c = cfg.input_channels
        self.enc1_conv1 = nn.Conv2d(c, 64, kernel_size=3, padding=1)
        self.enc1_conv2 = nn.Conv2d(64, 64, kernel_size=3, padding=1)
        self.enc2_conv1 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
        self.enc2_conv2 = nn.Conv2d(128, 128, kernel_size=3, padding=1)
        self.enc3_conv1 = nn.Conv2d(128, 256, kernel_size=3, padding=1)
        self.enc3_conv2 = nn.Conv2d(256, 256, kernel_size=3, padding=1)
        self.enc4_conv1 = nn.Conv2d(256, 512, kernel_size=3, padding=1)
        self.enc4_conv2 = nn.Conv2d(512, 512, kernel_size=3, padding=1)

        self.bridge_conv1 = nn.Conv2d(512, 1024, kernel_size=3, padding=1)
        self.bridge_conv2 = nn.Conv2d(1024, 1024, kernel_size=3, padding=1)

        self.up1 = nn.ConvTranspose2d(1024, 512, kernel_size=2, stride=2)
        self.dec1_conv1 = nn.Conv2d(1024, 512, kernel_size=3, padding=1)
        self.dec1_conv2 = nn.Conv2d(512, 512, kernel_size=3, padding=1)

        self.up2 = nn.ConvTranspose2d(512, 256, kernel_size=2, stride=2)
        self.dec2_conv1 = nn.Conv2d(512, 256, kernel_size=3, padding=1)
        self.dec2_conv2 = nn.Conv2d(256, 256, kernel_size=3, padding=1)

        self.up3 = nn.ConvTranspose2d(256, 128, kernel_size=2, stride=2)
        self.dec3_conv1 = nn.Conv2d(256, 128, kernel_size=3, padding=1)
        self.dec3_conv2 = nn.Conv2d(128, 128, kernel_size=3, padding=1)

        self.up4 = nn.ConvTranspose2d(128, 64, kernel_size=2, stride=2)
        self.dec4_conv1 = nn.Conv2d(128, 64, kernel_size=3, padding=1)
        self.dec4_conv2 = nn.Conv2d(64, 64, kernel_size=3, padding=1)

        self.final_conv = nn.Conv2d(64, cfg.num_classes, kernel_size=1, padding=0)

        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)
        self.relu = nn.ReLU(inplace=True)
        self.drop = nn.Dropout(p=cfg.dropout_prob)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # MATLAB ImageInputLayer uses zerocenter with a full mean image.
        mean = self.mean
        if mean.shape[2] != x.shape[2] or mean.shape[3] != x.shape[3]:
            if x.shape[2] <= mean.shape[2] and x.shape[3] <= mean.shape[3]:
                mean = mean[:, :, : x.shape[2], : x.shape[3]]
            else:
                mean2 = torch.full(
                    (1, mean.shape[1], x.shape[2], x.shape[3]),
                    -100.0,
                    device=x.device,
                    dtype=x.dtype,
                )
                h = min(mean.shape[2], x.shape[2])
                w = min(mean.shape[3], x.shape[3])
                mean2[:, :, :h, :w] = mean[:, :, :h, :w]
                mean = mean2
        x = x - mean

        e1 = self.relu(self.enc1_conv1(x))
        e1 = self.relu(self.enc1_conv2(e1))
        p1 = self.pool(e1)

        e2 = self.relu(self.enc2_conv1(p1))
        e2 = self.relu(self.enc2_conv2(e2))
        p2 = self.pool(e2)

        e3 = self.relu(self.enc3_conv1(p2))
        e3 = self.relu(self.enc3_conv2(e3))
        p3 = self.pool(e3)

        e4 = self.relu(self.enc4_conv1(p3))
        e4 = self.relu(self.enc4_conv2(e4))
        e4 = self.drop(e4)
        p4 = self.pool(e4)

        b = self.relu(self.bridge_conv1(p4))
        b = self.relu(self.bridge_conv2(b))
        b = self.drop(b)

        u1 = self.relu(self.up1(b))
        d1 = torch.cat([u1, e4], dim=1)
        d1 = self.relu(self.dec1_conv1(d1))
        d1 = self.relu(self.dec1_conv2(d1))

        u2 = self.relu(self.up2(d1))
        d2 = torch.cat([u2, e3], dim=1)
        d2 = self.relu(self.dec2_conv1(d2))
        d2 = self.relu(self.dec2_conv2(d2))

        u3 = self.relu(self.up3(d2))
        d3 = torch.cat([u3, e2], dim=1)
        d3 = self.relu(self.dec3_conv1(d3))
        d3 = self.relu(self.dec3_conv2(d3))

        u4 = self.relu(self.up4(d3))
        d4 = torch.cat([u4, e1], dim=1)
        d4 = self.relu(self.dec4_conv1(d4))
        d4 = self.relu(self.dec4_conv2(d4))

        return self.final_conv(d4)


def mean_shape(mean: np.ndarray) -> Tuple[int, int]:
    if mean.ndim != 3:
        raise ValueError(f"Expected mean shape (H,W,C), got {mean.shape}")
    return int(mean.shape[0]), int(mean.shape[1])
