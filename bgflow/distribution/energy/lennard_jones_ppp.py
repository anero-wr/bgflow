from .base import Energy
from bgflow.utils import distance_vectors, distances_from_vectors
import torch


__all__ = ["LennardJonesPotentialPPP"]


def lennard_jones_energy_torch(r, eps=1.0, rm=1.0, rct=2.5):

    r = torch.where((r < rct).clone().detach(), r, torch.tensor(1000000.))
    lj = eps * ((rm / r) ** 12 - 2 * (rm / r) ** 6) / 2.

    return lj


class LennardJonesPotentialPPP(Energy):
    def __init__(
            self, dim, n_particles, side, eps=1.0, rm=1.0, rct=2.5, oscillator=True, oscillator_scale=1., two_event_dims=True):
        """Energy for a Lennard-Jones cluster

        Parameters
        ----------
        dim : int
            Number of degrees of freedom ( = space dimension x n_particles)
        n_particles : int
            Number of Lennard-Jones particles
        eps : float
            LJ well depth epsilon
        rm : float
            LJ well radius R_min
        oscillator : bool
            Whether to use a harmonic oscillator as an external force
        oscillator_scale : float
            Force constant of the harmonic oscillator energy
        two_event_dims : bool
            If True, the energy expects inputs with two event dimensions (particle_id, coordinate).
            Else, use only one event dimension.
        """
        if two_event_dims:
            super().__init__([n_particles, dim//n_particles])
        else:
            super().__init__(dim)
        self._n_particles = n_particles
        self._n_dims = dim // n_particles

        self._eps = eps
        self._rm = rm
        self._rct = rct
        self._side = side
        self.oscillator = oscillator
        self._oscillator_scale = oscillator_scale

    def _energy(self, x):
        batch_shape = x.shape[:-len(self.event_shape)]
        x = x.view(*batch_shape, self._n_particles, self._n_dims)

        dists = distances_from_vectors(self._distance_vectors_ppp(x))

        lj_energies = lennard_jones_energy_torch(dists, self._eps, self._rm, self._rct)
        lj_energies = lj_energies.view(*batch_shape, -1).sum(dim=-1) / self._n_particles

        if self.oscillator:
            osc_energies = 0.5 * self._remove_mean(x).pow(2).sum(dim=(-2, -1)).view(*batch_shape)
            lj_energies = lj_energies + osc_energies * self._oscillator_scale

        lj_energies = lj_energies.flatten()

        return lj_energies[:, None]

    def _remove_mean(self, x):
        x = x.view(-1, self._n_particles, self._n_dims)
        return x - torch.mean(x, dim=1, keepdim=True)

    def _energy_numpy(self, x):
        x = torch.Tensor(x)
        return self._energy(x).cpu().numpy()

    def _distance_vectors_ppp(self, x):
        dv = distance_vectors(x.view(-1, self._n_particles, self._n_dims))
        h_side = self._side/2.
        return torch.where((abs(dv) < h_side).clone().detach(), dv, dv - self._side*dv.sign())

