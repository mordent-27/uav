"""Prespecified additional control, starting from Rust's original initializer."""
import controls as c


if __name__ == '__main__':
    model = c.tr.Model(0, 0, c.tr.LIBRARIES['normalized'])
    data = model.solution(model.y)
    data['solution'] = c.tr.decode(model, model.y, data)
    data['metrics']['objective'] = sum(data['solution']['s'])
    assert not c.source_path('default').exists(), 'refuse to overwrite seed'
    c.tr.write(c.source_path('default'), data)
    model.close()
    for backend in c.tr.BACKENDS:
        c.run(backend, 'direct', seed_kind='default')
    c.continue_newton(seed_kind='default')
