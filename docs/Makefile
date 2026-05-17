all : \
	notebooks/anydyce_intro.ipynb \
	assets/plot_anydyce_intro_dark.svg \
	assets/plot_anydyce_intro_light.svg

assets/plot_%_dark.png : assets/plot_%.py assets/_plot.py ../anydyce/*.py
	"$${PYTHON:-python3}" assets/plot_$*.py --log-level INFO --style dark --output-file $@

assets/plot_%_dark.svg : assets/plot_%.py assets/_plot.py ../anydyce/*.py
	"$${PYTHON:-python3}" assets/plot_$*.py --log-level INFO --style dark --output-file $@

assets/plot_%_light.png : assets/plot_%.py assets/_plot.py ../anydyce/*.py
	"$${PYTHON:-python3}" assets/plot_$*.py --log-level INFO --style light --output-file $@

assets/plot_%_light.svg : assets/plot_%.py assets/_plot.py ../anydyce/*.py
	"$${PYTHON:-python3}" assets/plot_$*.py --log-level INFO --style light --output-file $@

notebooks/%.ipynb : assets/nb_%.py
	jupytext --to notebook --update $< --output $@
	ruff check --fix $@
	ruff format $@
