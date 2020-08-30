Программа для генерации и визуализации roofline модели для различных суперкомпьютерных архитектур: NVIDIA GPU, Intel Xeon, NEC SX-Aurora TSUBASA, IBM Power

roofline_collect_gpu_metrics.py,roofline_collect_intel_metrics.py - модули для сбора метрик (на данный момент поддерживается только архитектура NVIDIA GPU)

visualization.py - модуль для визуализации roofline модели под произвольную архитектуру, на основе собранных метрик (или экспортированных значений полученных другим образом)


