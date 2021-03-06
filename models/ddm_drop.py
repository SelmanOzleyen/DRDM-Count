import torch
import torch.nn as nn
import torch.utils.model_zoo as model_zoo


model_urls = {
    'vgg11': 'https://download.pytorch.org/models/vgg11-bbd30ac9.pth',
    'vgg13': 'https://download.pytorch.org/models/vgg13-c768596a.pth',
    'vgg16': 'https://download.pytorch.org/models/vgg16-397923af.pth',
    'vgg19': 'https://download.pytorch.org/models/vgg19-dcbb9e9d.pth',
    'vgg11_bn': 'https://download.pytorch.org/models/vgg11_bn-6002323d.pth',
    'vgg13_bn': 'https://download.pytorch.org/models/vgg13_bn-abd245e5.pth',
    'vgg16_bn': 'https://download.pytorch.org/models/vgg16_bn-6c64b313.pth',
    'vgg19_bn': 'https://download.pytorch.org/models/vgg19_bn-c79401a0.pth',
}


class VGG(nn.Module):

    def __init__(
        self,
        device,
        features: nn.Module,
        p=[0.01, 0.01, 0.1, 0.1, 0.2, 0.2],
    ) -> None:
        super(VGG, self).__init__()
        self.features = features

        self.cnv1 = nn.Conv2d(512, 512, kernel_size=3, padding=2, dilation=2).to(device=device)
        self.dl1 = nn.Dropout2d(inplace=False, p=p[0])
        self.dl1a = nn.Dropout2d(inplace=False, p=p[1])
        self.bn1 = nn.BatchNorm2d(512)
        self.layer1_relu = nn.LeakyReLU(inplace=True).to(device=device)

        self.cnv2 = nn.Conv2d(512, 512, kernel_size=3, padding=2, dilation=2).to(device=device)
        self.dl2 = nn.Dropout2d(inplace=False, p=p[2])
        self.dl2a = nn.Dropout2d(inplace=False, p=p[3])
        self.bn2 = nn.BatchNorm2d(512)
        self.layer2_relu = nn.LeakyReLU(inplace=True).to(device=device)

        self.cnv3 = nn.Conv2d(512, 512, kernel_size=3, padding=2, dilation=2).to(device=device)
        self.dl3 = nn.Dropout2d(inplace=False, p=p[4])
        self.dl3a = nn.Dropout2d(inplace=False, p=p[5])
        self.bn3 = nn.BatchNorm2d(512)
        self.layer3_relu = nn.LeakyReLU(inplace=True).to(device=device)

        self.cnv4 = nn.Conv2d(512, 256, kernel_size=3, padding=2, dilation=2).to(device=device)
        # self.dl4 = nn.Dropout2d(inplace=False)
        self.bn4 = nn.BatchNorm2d(256)
        self.layer4_relu = nn.LeakyReLU(inplace=True).to(device=device)

        self.cnv5 = nn.Conv2d(256, 128, kernel_size=3, padding=2, dilation=2).to(device=device)
        # self.dl5 = nn.Dropout2d(inplace=False)
        self.bn5 = nn.BatchNorm2d(128)
        self.layer5_relu = nn.LeakyReLU(inplace=True).to(device=device)

        self.density_layer = nn.Sequential(nn.Conv2d(128, 1, 1), nn.ReLU()).to(device=device)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x_skip = x
        x = self.cnv1(x)
        x = self.dl1(x)
        x = self.bn1(x)
        x += self.dl1a(x_skip)
        x = self.layer1_relu(x)

        x_skip = x
        x = self.cnv2(x)
        x = self.dl2(x)
        x = self.bn2(x)
        x += self.dl2a(x_skip)
        x = self.layer2_relu(x)

        x_skip = x
        x = self.cnv3(x)
        x = self.dl3(x)
        x = self.bn3(x)
        x += self.dl3a(x_skip)
        x = self.layer3_relu(x)

        x = self.cnv4(x)
        # x = self.dl4(x)
        x = self.bn4(x)
        x = self.layer4_relu(x)

        x = self.cnv5(x)
        # x = self.dl5(x)
        x = self.bn5(x)
        x = self.layer5_relu(x)

        mu = self.density_layer(x)
        B, C, H, W = mu.size()
        mu_sum = mu.view([B, -1]).sum(1).unsqueeze(1).unsqueeze(2).unsqueeze(3)
        mu_normed = mu / (mu_sum + 1e-6)
        return mu, mu_normed


def conv2d_bn(in_channels, out_channels, kernel_size=3, padding=2, dilation=2):
    return nn.Sequential(
        nn.Conv2d(in_channels, out_channels, kernel_size=kernel_size, padding=padding, dilation=dilation),
        nn.Dropout2d(inplace=False, p=0.01),
        nn.BatchNorm2d(out_channels))


def make_layers(cfg, batch_norm=True):
    layers = []
    in_channels = 3
    for v in cfg:
        if v == 'M':
            layers += [nn.MaxPool2d(kernel_size=2, stride=2)]
        else:
            conv2d = nn.Conv2d(in_channels, v, kernel_size=3, padding=1)
            if batch_norm:
                layers += [conv2d, nn.BatchNorm2d(v), nn.ReLU()]
            else:
                layers += [conv2d, nn.ReLU()]
            in_channels = v
    return nn.Sequential(*layers)


cfg = {
    'D': [64, 64, 'M', 128, 128, 'M', 256, 256, 256, 'M', 512, 512, 512],
}


def vgg16dres(map_location, pretrained: bool = True, progress: bool = True) -> VGG:
    model = VGG(map_location, make_layers(cfg['D']))
    model.load_state_dict(model_zoo.load_url(model_urls['vgg16_bn'], map_location=map_location),
                          strict=False)
    return model
