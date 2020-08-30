#!/usr/bin/python


import plotly
import plotly.plotly as py
import plotly.graph_objs as go
import bisect

tmp_data_prefix = "tmp/"

P100_characteristics = {"bandwidths": {"DRAM": 628,                         # GB/s
                                       "L1": 8502,  # GB/s
                                       "L2": 1757},                   # GB/s,
                        "peak_performances": {"integer": 5300, #2242,              # GIOP/s
                                              "float": 10600,
                                              "float_no_fma": 5300,
                                              "double": 5300,
                                              "double_no_fma": 2650}}               # GFLOP/s

Intel_Haswell_characteristics = {"bandwidths": {"dram": 51,         # GB/s
                                                "l1_cache": 823,
                                                "l2_cache": 409},       # GB/s
                                                "peak_performances": {"integer": 85,
                                                                      "float": 154}}  # GIOP/s

Intel_Skylake_characteristics = {"bandwidths": {"dram": 78,         # GB/s
                                                "l1_cache": 1097,
                                                "l3_cache": 142},
                                                "peak_performances": {"integer": 1212, #1068,
                                                                      "float": 1212}}  # GIOP/s

NEC_SX_Aurora_TSUBASA_characteristics = {"bandwidths": {"dram": 995,         # GB/s
                                                        "LLC": 1700},        # GB/s
                                         "peak_performances": {"integer": 2080, #1432, # GIOP/s
                                                               "float": 2080}}  # GFLOP/s

IBM_POWER_8_characteristics = {"bandwidths": {"dram": 184},        # GB/s
                               "peak_performances": {"integer": 395, # GIOP/s
                                                     "float": 395}}  # GFLOP/s


x_data_first = 1.0 / 256.0
x_data_last = 1024


class RooflinePlotter:
    def __init__(self, name, platform_characteristics, precision):
        self.platform_characteristics = platform_characteristics
        self.total_execution_time = 0.0
        self.name = name
        print(precision)
        if "int" in str(precision):
            self.precision = "integer"
        elif "sp" in str(precision):
            self.precision = "float"
        elif "dp" in str(precision):
            self.precision = "double"

    def get_compute_roof(self, x, roof_bandwidth):
        return min(self.platform_characteristics["peak_performances"][self.precision], roof_bandwidth * x)

    def get_no_fma_compute_roof(self, x, roof_bandwidth):
        return min(self.platform_characteristics["peak_performances"][self.precision + "_no_fma"], roof_bandwidth * x)

    def calculate_intersection_points(self):
        points_array = []
        for key in self.platform_characteristics["bandwidths"]:
            print(self.platform_characteristics["bandwidths"][key])
            points_array.append(float(self.platform_characteristics["peak_performances"][self.precision]) /
                                float(self.platform_characteristics["bandwidths"][key]))
        return points_array

    def create_x_data(self, x_min, x_max, additional_x_points):
        x_array = []
        current = x_min
        prev = 0
        intersection_points = self.calculate_intersection_points()
        while current <= x_max:
            x_array.append(current)
            prev = current
            current *= 2

        for point in intersection_points:
            bisect.insort(x_array, point)

        for point in additional_x_points:
            bisect.insort(x_array, point)

        return x_array

    def performance_in_GIOPs(self, GIOP_count, time):
        return GIOP_count / (time * pow(10, 9))

    def ops_per_byte(self, ops, bytes):
        return ops / bytes

    def generate_CARM_roof_plots(self, additional_x_points):
        x_data = self.create_x_data(x_data_first, x_data_last, additional_x_points)
        data = []

        for key in self.platform_characteristics["bandwidths"]:
            y_data = []
            for x in x_data:
                y_data.append(self.get_compute_roof(x, self.platform_characteristics["bandwidths"][key]))
            data.append(go.Scatter(x=x_data, y=y_data, name=str(key)))

        y_data = []
        for x in x_data:
            y_data.append(self.get_no_fma_compute_roof(x, self.platform_characteristics["bandwidths"]["L1"]))
        data.append(go.Scatter(x=x_data, y=y_data, name="no fma"))

        return data

    def get_point_description_text(self, profiling_data):
        point_description_text = profiling_data["name"] + "</br>"
        x = float(profiling_data["ops_per_byte"])

        # memory bound case
        top_roof_val = 0
        top_roof_name = ""
        min_distance = self.platform_characteristics["peak_performances"][self.precision]
        closest_roof_val = 0
        closest_roof_name = ""
        point_val = profiling_data["giops"]
        #for key in self.platform_characteristics["bandwidths"]:
        key = profiling_data["memory_roof"]
        roof_val = self.get_compute_roof(self.platform_characteristics["bandwidths"][key], x)
        if roof_val >= top_roof_val:
            top_roof_val = roof_val
            top_roof_name = key
        if (roof_val >= point_val) and (min_distance >= abs(roof_val - point_val)):
            min_distance = abs(roof_val - point_val)
            closest_roof_val = roof_val
            closest_roof_name = key

        # compute bound case
        if closest_roof_val == self.platform_characteristics["peak_performances"][self.precision]:
            closest_roof_name = "Peak integer performance"

        if top_roof_val == self.platform_characteristics["peak_performances"][self.precision]:
            top_roof_name = "Peak integer performance"

        if closest_roof_val > 0:
            distance_from_closest_roof = 100.0 * float(point_val) / float(closest_roof_val)
        else:
            distance_from_closest_roof = 100
        if top_roof_val > 0:
            distance_from_top_roof = 100.0 * float(point_val) / float(top_roof_val)
        else:
            distance_from_top_roof = 100

        if top_roof_val != closest_roof_val:  # print closest roof only if it is different from top toof
            point_description_text += closest_roof_name + " - closest roof: " + str(distance_from_closest_roof) + \
                                      "% </br>"
        point_description_text += top_roof_name + " -  top roof: " + str(distance_from_top_roof) + "% </br>"
        return point_description_text

    def generate_roofline_point_plot(self, profiling_data):
        point_description_text = self.get_point_description_text(profiling_data)
        point_trace = go.Scatter(
            x=[profiling_data["ops_per_byte"], profiling_data["ops_per_byte"]],
            y=[0, profiling_data["giops"]],
            name=profiling_data["name"],
            mode='markers',
            text=['', point_description_text, ''],
            textposition='top center'
        )
        return point_trace

    def get_profiling_points_x_data(self, profiling_data_array):
        additional_x_points = []
        for profiling_data in profiling_data_array:
            additional_x_points.append(profiling_data["ops_per_byte"])
        return additional_x_points

    def draw_plot(self, profiling_data_array):
        profiling_points_x_data = [] #self.get_profiling_points_x_data(profiling_data_array)
        plots_data = self.generate_CARM_roof_plots(profiling_points_x_data)

        for profiling_data in profiling_data_array:
            plots_data.append(self.generate_roofline_point_plot(profiling_data))

        if self.precision == "double":
            y_title = "GFLOP/s"
        if self.precision == "float":
            y_title = "GFLOP/s"
        if self.precision == "integer":
            y_title = "GIOPS/s"
        xaxis = dict(autorange=True, showgrid=True, zeroline=True, showline=True, autotick=True, ticks='',
                     showticklabels=True, type='log', title='Arithmetic Intensity')

        yaxis = dict(autorange=True, showgrid=True, zeroline=True, showline=True, autotick=True, ticks='',
                     showticklabels=True, type='log', title=y_title)

        plotly.offline.plot({
            "data": plots_data,
            "layout": go.Layout(title=self.name, xaxis=xaxis, yaxis=yaxis)
        })


def generate_roofline_from_profiling_data(file_name, roofline_name, platform_characteristics):
    # read CMD file
    profiling_file = open(file_name, 'r')
    profiling_data = []

    precision = ""
    line_pos = 0
    for line in profiling_file:
        line_pos += 1
        if line_pos == 1:
            precision = line
            continue
        if line.startswith("#") or line.startswith("//"):
            continue
        line_split = line.split("|")
        name = line_split[0]
        ops_number = float(line_split[1])
        ops_per_byte = float(line_split[2])
        memory_roof = line_split[3]
        profiling_data.append({"name": name,
                               "ops_per_byte": ops_per_byte,
                               "giops": ops_number,
                               "memory_roof": memory_roof})
    profiling_file.close()

    # initialize and draw roofline
    roofline = RooflinePlotter(roofline_name, platform_characteristics, precision)
    roofline.draw_plot(profiling_data)


def p100():
    generate_roofline_from_profiling_data(tmp_data_prefix + "P100_profiling_data.txt",
                                          "P100 (Pascal architecture) GPU Cache-Aware Roofline Model",
                                          P100_characteristics)


p100()

