"""Toy code implementing the time evolving block decimation (TEBD)."""
# Copyright 2018 TeNPy Developers

import numpy as np
from scipy.linalg import expm
from a_mps import split_truncate_theta
import tfi_exact


def calc_U_bonds(H_bonds, dt):
    """Given the H_bonds, calculate ``U_bonds[i] = expm(-dt*H_bonds[i])``.

    Each local operator has legs (i out, (i+1) out, i in, (i+1) in), in short ``i j i* j*``.
    Note that no imaginary 'i' is included, thus real `dt` means 'imaginary time' evolution!
    """
    d = H_bonds[0].shape[0]
    U_bonds = []
    for H in H_bonds:
        H = np.reshape(H, [d * d, d * d])
        U = expm(-dt * H)
        U_bonds.append(np.reshape(U, [d, d, d, d]))
    return U_bonds


def run_TEBD(psi, U_bonds, N_steps, chi_max, eps):
    """Evolve for `N_steps` time steps with TEBD."""
    Nbonds = psi.L - 1 if psi.bc == 'finite' else psi.L
    assert len(U_bonds) == Nbonds
    for n in range(N_steps):
        for k in [0, 1]:  # even, odd
            for i_bond in range(k, Nbonds, 2):
                update_bond(psi, i_bond, U_bonds[i_bond], chi_max, eps)
    # done


def update_bond(psi, i, U_bond, chi_max, eps):
    """Apply `U_bond` acting on i,j=(i+1) to `psi`."""
    j = (i + 1) % psi.L
    # construct theta matrix
    theta = psi.get_theta2(i)  # vL i j vR
    # apply U
    Utheta = np.tensordot(U_bond, theta, axes=([2, 3], [1, 2]))  # i j [i*] [j*], vL [i] [j] vR
    Utheta = np.transpose(Utheta, [2, 0, 1, 3])  # vL i j vR
    # split and truncate
    Ai, Sj, Bj = split_truncate_theta(Utheta, chi_max, eps)
    # put back into MPS
    Gi = np.tensordot(np.diag(psi.Ss[i]**(-1)), Ai, axes=[1, 0])  # vL [vL*], [vL] i vC
    psi.Bs[i] = np.tensordot(Gi, np.diag(Sj), axes=[2, 0])  # vL i [vC], [vC] vC
    psi.Ss[j] = Sj  # vC
    psi.Bs[j] = Bj  # vC j vR


def example_TEBD_gs_finite(L, g):
    print("finite TEBD, imaginary time evolution, L={L:d}, g={g:.2f}".format(L=L, g=g))
    import a_mps
    import b_model
    M = b_model.TFIModel(L, J=1., g=g)
    psi = a_mps.init_FM_MPS(M.L, M.d, M.bc)
    for dt in [0.1, 0.01, 0.001, 1.e-4, 1.e-5]:
        U_bonds = calc_U_bonds(M.H_bonds, dt)
        run_TEBD(psi, U_bonds, N_steps=500, chi_max=30, eps=1.e-10)
        E = np.sum(psi.bond_expectation_value(M.H_bonds))
        print("dt = {dt:.5f}: E = {E:.13f}".format(dt=dt, E=E))
    print("final bond dimensions: ", psi.get_chi())
    if L < 20:  # compare to exact result
        E_exact = tfi_exact.finite_gs_energy(L, 1., g)
        print("Exact diagonalization: E = {E:.13f}".format(E=E_exact))
        print("relative error: ", abs((E - E_exact) / E_exact))
    return E, psi, M


def example_TEBD_gs_infinite(g):
    print("infinite TEBD, imaginary time evolution, g={g:.2f}".format(g=g))
    import a_mps
    import b_model
    M = b_model.TFIModel(L=2, J=1., g=g, bc='infinite')
    psi = a_mps.init_FM_MPS(M.L, M.d, M.bc)
    for dt in [0.1, 0.01, 0.001, 1.e-4, 1.e-5]:
        U_bonds = calc_U_bonds(M.H_bonds, dt)
        run_TEBD(psi, U_bonds, N_steps=500, chi_max=30, eps=1.e-10)
        E = np.mean(psi.bond_expectation_value(M.H_bonds))
        print("dt = {dt:.5f}: E/L = {E:.13f}".format(dt=dt, E=E))
    print("final bond dimensions: ", psi.get_chi())
    print("correlation length:", psi.correlation_length())
    # compare to exact result
    E_exact = tfi_exact.infinite_gs_energy(1., g)
    print("Analytic result: E/L = {E:.13f}".format(E=E_exact))
    print("relative error: ", abs((E - E_exact) / E_exact))
    return E, psi, M


def example_TEBD_lightcone(L, g, tmax, dt):
    print("finite TEBD, real time evolution, L={L:d}, g={g:.2f}".format(L=L, g=g))
    # find ground state with TEBD or DMRG
    #  E, psi, M = example_TEBD_gs_finite(L, g)
    from d_dmrg import example_DMRG_finite
    E, psi, M = example_DMRG_finite(L, g)
    i0 = L // 2
    # apply sigmaz on site i0
    SzB = np.tensordot(M.sigmaz, psi.Bs[i0], axes=[1, 1])  # i [i*], vL [i] vR
    psi.Bs[i0] = np.transpose(SzB, [1, 0, 2])  # vL i vR
    U_bonds = calc_U_bonds(M.H_bonds, 1.j * dt)  # (imaginary dt -> realtime evolution)
    S = [psi.entanglement_entropy()]
    Nsteps = int(tmax / dt + 0.5)
    for n in range(Nsteps):
        if abs((n * dt + 0.1) % 0.2 - 0.1) < 1.e-10:
            print("t = {t:.2f}, chi =".format(t=n * dt), psi.get_chi())
        run_TEBD(psi, U_bonds, 1, chi_max=50, eps=1.e-10)
        S.append(psi.entanglement_entropy())
    import pylab as pl
    pl.figure()
    pl.imshow(S[::-1], vmin=0., aspect='auto', interpolation='nearest',
              extent=(0, L - 1., -0.5*dt, (Nsteps + 0.5) * dt))  # yapf:disable
    pl.xlabel('site $i$')
    pl.ylabel('time $t/J$')
    pl.ylim(0., tmax)
    pl.colorbar().set_label('entropy $S$')
    pl.show()


if __name__ == "__main__":
    example_TEBD_gs_finite(L=10, g=1.)
    print("-" * 100)
    example_TEBD_gs_infinite(g=1.5)
    print("-" * 100)
    example_TEBD_lightcone(L=20, g=1.5, tmax=3., dt=0.001)
