"""Lazy G-first selection; objective values never determine which route is called."""


def select(g_result,fallback_supplier):
    if g_result['last_restoration_solver_accepted']:
        if not (g_result['final_common_kkt'] and g_result['physical_point_available'] and
                g_result['selected_same_final_branch_kkt']):
            raise ValueError('accepted G restoration lacks a validated common-KKT/physical certificate')
        return dict(route='G',outcome=g_result,fallback_called=False)
    return dict(route='fallback',outcome=fallback_supplier(),fallback_called=True)
