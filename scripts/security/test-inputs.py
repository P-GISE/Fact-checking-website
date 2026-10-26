"""Exercise the exported Pip locks consumed by setup-dev-tools, without installing them."""
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


def main() -> None:
    with TemporaryDirectory(prefix='fact-devtools-security-inputs-') as name:
        folder = Path(name)
        tree = folder / 'inputs/tree'
        locks = ('devtools/headroom.lock.txt', 'devtools/strix.lock.txt', 'devtools/ironlaws.lock.txt', 'devtools/security-builder.lock.txt', 'server/requirements.lock')
        original = 'synthetic-package==1.2.3\n'
        for relative in locks:
            source = tree / relative
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(original, encoding='utf-8')
        subprocess.run([sys.executable, str(Path(__file__).with_name('prepare-inputs.py')), str(folder)], check=True)
        for relative in locks:
            normalized = folder / 'inputs/normalized-locks' / relative / 'requirements.txt'
            assert normalized.read_text(encoding='utf-8') == original
            assert (tree / relative).read_text(encoding='utf-8') == original
    print('Five consumed Pip locks normalized; original inputs preserved')


if __name__ == '__main__':
    main()
