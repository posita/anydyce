all : \
	plot_burst_1_dark.png \
	plot_burst_1_light.png \
	plot_burst_2_dark.png \
	plot_burst_2_light.png \
	plot_burst_3_dark.png \
	plot_burst_3_light.png

plot_%_dark.png : plot_%.py Makefile plot.py ../../anydyce/viz.py
	"$${PYTHON:-python}" plot.py --style=dark $*

plot_%_light.png : plot_%.py Makefile plot.py ../../anydyce/viz.py
	"$${PYTHON:-python}" plot.py --style=light $*
