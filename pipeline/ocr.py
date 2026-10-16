import sys, os, glob, subprocess, tempfile, warnings
warnings.filterwarnings('ignore')
import pymupdf
from concurrent.futures import ProcessPoolExecutor
PUBS, OUT = sys.argv[1], sys.argv[2]
MAXPAGES = 4
def work(path):
    name = os.path.splitext(os.path.basename(path))[0]
    out = os.path.join(OUT, name + '.txt')
    if os.path.exists(out) and os.path.getsize(out) > 0: return name, 'cached'
    try:
        doc = pymupdf.open(path)
    except Exception as ex:
        open(out, 'w').write(f'__ERROR__ {ex}'); return name, 'err'
    pages = list(doc)[:MAXPAGES]
    text = ''.join(p.get_text() for p in pages)
    mode = 'text'
    if len(text.strip()) < 300:
        mode = 'ocr'; parts = []
        with tempfile.TemporaryDirectory() as td:
            for i, p in enumerate(pages):
                img = os.path.join(td, f'{i}.png')
                p.get_pixmap(dpi=250).save(img)
                try:
                    r = subprocess.run(['tesseract', img, '-', '-l', 'eng', '--psm', '6'], capture_output=True, text=True,
                                       timeout=180, env=dict(os.environ, OMP_THREAD_LIMIT='1'))
                except subprocess.TimeoutExpired:
                    continue
                parts.append(r.stdout)
        text = '\n'.join(parts)
    open(out, 'w').write(text)
    return name, mode
if __name__ == '__main__':
    files = sorted(glob.glob(os.path.join(PUBS, '*.pdf')))
    from collections import Counter
    c = Counter()
    with ProcessPoolExecutor(max_workers=max(2, os.cpu_count() or 2)) as ex:
        for i, (n, m) in enumerate(ex.map(work, files)):
            c[m] += 1
            if i % 10 == 0: print(i, '/', len(files), dict(c), flush=True)
    print('OCR gata', dict(c), flush=True)
