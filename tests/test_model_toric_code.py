# Copyright 2018 TeNPy Developers

from tenpy.models.toric_code import ToricCode
from test_model import check_general_model
from nose.plugins.attrib import attr
from tenpy.networks.mps import MPS
from tenpy.algorithms import dmrg
import numpy as np
import warnings


def test_ToricCode_general():
    check_general_model(ToricCode, dict(Lx=2, Ly=4, bc_MPS='infinite'), {
        'conserve': [None, 'parity'],
    })


@attr('slow')
def test_ToricCode(Lx=1, Ly=2):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        model_params = {'Lx': Lx, 'Ly': Ly}
        M = ToricCode(model_params)
        psi = MPS.from_product_state(M.lat.mps_sites(), [0] * M.lat.N_sites, bc='infinite')
        dmrg_params = {
            'mixer': True,
            'trunc_params': {'chi_max': 10, 'svd_min': 1.e-10},
            'max_E_err': 1.e-10,
            'N_sweeps_check': 4,
            'verbose': 1
        }
        result = dmrg.run(psi, M, dmrg_params)
        E = result['E']
        print("E =", E)
        psi.canonical_form()
        # energy per "cell"=2 -> energy per site in the dual lattice = 1
        assert abs(E-(-1.)) < dmrg_params['max_E_err']
        print("chi=", psi.chi)
        if Ly == 2:
            assert tuple(psi.chi[:4]) == (2, 4, 4, 4)
        assert abs(psi.entanglement_entropy(bonds=[0])[0] - np.log(2)*(Ly-1)) < 1.e-5

if __name__ == "__main__":
    test_ToricCode()
