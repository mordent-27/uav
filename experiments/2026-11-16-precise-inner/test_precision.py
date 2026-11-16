from decimal import Decimal as D,localcontext
from time import monotonic
import unittest
import numpy as np
from precision import central_gradient
from inner import solve


class TestPrecision(unittest.TestCase):
    def test_quadratic_gradient_known_answer(self):
        with localcontext() as ctx:
            ctx.prec=80
            g=central_gradient(lambda x:x[0]**2+3*x[1]**2,[1.,-2.],80,'1e-20')
            self.assertEqual(g,[D(2),D(-12)])

    def test_small_gradient_survives_large_constant(self):
        with localcontext() as ctx:
            ctx.prec=80
            g=central_gradient(lambda x:D('1e8')+x[0]**2/2,[D('1e-12')],80,'1e-20')
            self.assertEqual(g,[D('1e-12')])

    def test_gradient_deadline(self):
        with self.assertRaises(TimeoutError):central_gradient(lambda x:x[0]**2,[1.],80,'1e-20',0.)

    def quadratic_evaluator(self,decimal):
        def evaluate(y,deadline):
            with localcontext() as ctx:
                ctx.prec=80
                exact=D('1e8')+sum(D.from_float(float(v))**2/2 for v in y)
            return float(exact),y.copy(),exact if decimal else None
        return evaluate

    def test_common_loop_native_quadratic(self):
        result=solve(self.quadratic_evaluator(False),lambda y,c:np.eye(2),np.array([1.,2.]),monotonic()+5)
        self.assertEqual(result['status'],'converged');self.assertLessEqual(result['gradient_inf'],1e-8)

    def test_common_loop_decimal_quadratic(self):
        result=solve(self.quadratic_evaluator(True),lambda y,c:np.eye(2),np.array([1.,2.]),monotonic()+5)
        self.assertEqual(result['status'],'converged');self.assertLessEqual(result['gradient_inf'],1e-8)


if __name__=='__main__':unittest.main()
