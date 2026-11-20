"""Compile the established human/report.tex, validate A4/8 pages, then install PDF."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
HUMAN = ROOT.parent / 'human'


def main():
    output = Path(tempfile.mkdtemp(prefix='uav-report-review-build-'))
    for n in (1, 2):
        with (output / f'pass{n}.log').open('w') as stream:
            subprocess.run(['uplatex', '-interaction=nonstopmode', '-halt-on-error',
                            f'-output-directory={output}', 'report.tex'], cwd=HUMAN,
                           stdout=stream, stderr=subprocess.STDOUT, check=True)
    log = (output / 'pass2.log').read_text()
    assert not re.search(r'Warning|Overfull|Underfull|undefined', log), output
    with (output / 'dvipdfmx.log').open('w') as stream:
        subprocess.run(['dvipdfmx', '-o', str(output / 'report.pdf'), str(output / 'report.dvi')],
                       cwd=HUMAN, stdout=stream, stderr=subprocess.STDOUT, check=True)
    info = subprocess.check_output(['pdfinfo', str(output / 'report.pdf')], text=True)
    pages = int(re.search(r'Pages:\s+(\d+)', info)[1])
    width, height = map(float, re.search(r'Page size:\s+([\d.]+) x ([\d.]+)', info).groups())
    assert pages <= 8 and abs(width - 595.276) < .1 and abs(height - 841.89) < .1, info
    subprocess.run(['pdftotext', '-layout', str(output / 'report.pdf'), str(output / 'report.txt')], check=True)
    text = (output / 'report.txt').read_text()
    assert '??' not in text and '[?]' not in text
    shutil.copy2(output / 'report.pdf', HUMAN / 'report.pdf')
    print(json.dumps(dict(output=str(output), pages=pages, A4=True, target=str(HUMAN / 'report.pdf'))))


if __name__ == '__main__':
    main()
