import torch
from torch.nn import Module
from .bregman_pytorch import sinkhorn


class OT_Loss(Module):
    def __init__(self, c_size, stride, norm_cood, device, logger, num_of_iter_in_ot=100, reg=10.0, log_freq=10):
        super(OT_Loss, self).__init__()
        assert c_size % stride == 0
        self.it = 0
        self.log_freq = log_freq
        self.c_size = c_size
        self.device = device
        self.norm_cood = norm_cood
        self.num_of_iter_in_ot = num_of_iter_in_ot
        self.reg = reg
        self.logger = logger

        # coordinate is same to image space, set to constant since crop size is same
        self.cood = torch.arange(0, c_size, step=stride,
                                 dtype=torch.float32, device=device) + stride / 2
        self.cood_squared = self.cood*self.cood  # storing the precalculated matrix
        self.density_size = self.cood.size(0)
        self.cood.unsqueeze_(0)   # [1, #cood]
        if self.norm_cood:
            self.cood = self.cood / c_size * 2 - 1  # map to [-1, 1]
        self.output_size = self.cood.size(1)

    def forward(self, normed_density, unnormed_density, points):
        batch_size = normed_density.size(0)
        assert len(points) == batch_size
        assert self.output_size == normed_density.size(2)
        loss = torch.zeros([1]).to(self.device)
        ot_obj_values = torch.zeros([1]).to(self.device)
        wd = 0  # wasserstain distance
        for idx, im_points in enumerate(points):
            if len(im_points) == 0:
                im_points = torch.tensor(
                    [
                        [0,2*self.c_size]
                        [0,-2*self.c_size]
                        [2*self.c_size,0]
                        [-2*self.c_size,0]
                    ], device=self.device
                )
            
            im_points = 0.1*torch.randn_like(im_points)+im_points
            # compute l2 square distance, it should be source target distance. [#gt, #cood * #cood]
            if self.norm_cood:
                im_points = im_points / self.c_size * 2 - 1  # map to [-1, 1]
            x = im_points[:, 0].unsqueeze_(1)  # [N, 1]
            y = im_points[:, 1].unsqueeze_(1)
            x_dis = -2 * torch.matmul(x, self.cood) + x * x + self.cood_squared  # [#gt, #cood]
            y_dis = -2 * torch.matmul(y, self.cood) + y * y + self.cood_squared
            y_dis.unsqueeze_(2)
            x_dis.unsqueeze_(1)
            dis = y_dis + x_dis
            dis = dis.view((dis.size(0), -1))  # size of [#gt, #cood * #cood]

            source_prob = normed_density[idx][0].view([-1]).detach()
            target_prob = (torch.ones([len(im_points)]) / len(im_points)).to(self.device)
            # use sinkhorn to solve OT, compute optimal beta.
            P, log = sinkhorn(target_prob, source_prob, dis, self.reg, maxIter=self.num_of_iter_in_ot, log=True)
            beta = log['beta']  # size is the same as source_prob: [#cood * #cood]
            ot_obj_values += torch.sum(normed_density[idx] * beta.view([1, self.output_size, self.output_size]))

            # compute the gradient of OT loss to predicted density (unnormed_density).
            # im_grad = beta / source_count - < beta, source_density> / (source_count)^2
            source_density = unnormed_density[idx][0].view([-1]).detach()
            if self.it % self.log_freq == 0:
                self.logger.add_image("src_prob", source_density.view([1, self.output_size, self.output_size]), self.it)
            source_count = source_density.sum()
            im_grad_1 = (source_count) / (source_count * source_count+1e-8) * beta  # size of [#cood * #cood]
            im_grad_2 = (source_density * beta).sum() / (source_count * source_count + 1e-8)  # size of 1
            im_grad = im_grad_1 - im_grad_2
            im_grad = im_grad.detach().view([1, self.output_size, self.output_size])
            if self.it % self.log_freq == 0:
                self.logger.add_image("im_grad", im_grad, self.it)
                self.logger.add_image("beta", beta.view([1, self.output_size, self.output_size]), self.it)
            # Define loss = <im_grad, predicted density>. The gradient of loss w.r.t prediced density is im_grad.
            loss += torch.sum(unnormed_density[idx] * im_grad)
            wd += torch.sum(dis * P).item()
        self.it = self.it + 1
        return loss, wd, ot_obj_values


