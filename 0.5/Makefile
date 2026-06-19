all : \
    anydice-playground.svg \
	notebooks/anydyce_intro.ipynb

notebooks/%.ipynb : assets/nb_%.py
	jupytext --to notebook --update $< --output $@
	ruff check --fix $@
	ruff format $@

anydice-playground.svg : Makefile
	curl --output $@ 'https://img.shields.io/badge/%F0%9F%A4%B7%F0%9F%8E%B2%20AnyDice-Compatible%20%F0%9F%9B%9D-teal.svg'
