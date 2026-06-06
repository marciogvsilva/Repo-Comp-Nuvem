# Relatorio

Arquivo principal: `relatorio.tex`.

O relatório final usa os artefatos medidos em `../results/benchmark/`, gerados por:

```bash
./.venv/bin/python scripts/run_final_experiment.py \
  --port 8010 --products 10000 --repetitions 5 \
  --output-dir results/benchmark
```

Para compilar localmente com TeX Live/MikTeX:

```bash
pdflatex relatorio.tex
bibtex relatorio
pdflatex relatorio.tex
pdflatex relatorio.tex
```

No Overleaf, envie `relatorio.tex` e `references.bib` para a mesma pasta do projeto e selecione `relatorio.tex` como arquivo principal.
