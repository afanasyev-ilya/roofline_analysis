#!/usr/bin/python

from parse_cmd_file import read_cmd_file
from paths import *
from subprocess import Popen, PIPE, call


class ProfilingDataIntel:
    def __init__(self, name, arch):
        self.data = {"integer_instructions": 0,
                     "float_instructions": 0,
                     "double_instructions": 0,
                     "bytes_requested": 0}

        self.total_execution_time = 0.0
        self.name = name
        self.arch = arch

    def get_ops_per_byte(self):
        ops_executed = self.data["float_instructions"]
        bytes_requested = self.data["bytes_requested"]
        return float(ops_executed) / float(bytes_requested)

    def get_ops(self):
        return self.data["float_instructions"] / self.total_execution_time

    def get_sde_command(self, application):
        result = ""
        result += software_path + "sde64 "
        result += " -" + self.arch + " "
        result += " -iform 1 -omix "
        result +=  profiling_data_path + "sde.out "
        result += " -top_blocks 5000 -start_ssc_mark 111:repeat -stop_ssc_mark 222:repeat -- "
        result += exec_data_path + application
        print result
        return result

    def process_metrics_line(self, line, metric_name):
        if str(metric_name) in line:
            metric_value = float(line.split()[1])
            return metric_value
        else:
            return 0

    def parse_sde_output(self, file_name):
        profiling_file = open(file_name, 'r')
        found_final_table = False
        for line in profiling_file:
            if "$global-dynamic-counts" in line:
                found_final_table = True

            if found_final_table is False:
                continue

            self.data["bytes_requested"] += self.process_metrics_line(line, "mem-read-1") * 1
            self.data["bytes_requested"] += self.process_metrics_line(line, "mem-read-2") * 2
            self.data["bytes_requested"] += self.process_metrics_line(line, "mem-read-4") * 4
            self.data["bytes_requested"] += self.process_metrics_line(line, "mem-read-8") * 8
            self.data["bytes_requested"] += self.process_metrics_line(line, "mem-read-16") * 16

            self.data["bytes_requested"] += self.process_metrics_line(line, "mem-write-1") * 1
            self.data["bytes_requested"] += self.process_metrics_line(line, "mem-write-2") * 2
            self.data["bytes_requested"] += self.process_metrics_line(line, "mem-write-4") * 4
            self.data["bytes_requested"] += self.process_metrics_line(line, "mem-write-8") * 8
            self.data["bytes_requested"] += self.process_metrics_line(line, "mem-write-16") * 16

            self.data["float_instructions"] += self.process_metrics_line(line, "elements_fp_single_1")
            self.data["double_instructions"] += self.process_metrics_line(line, "elements_fp_double_1")

            '''self.data["integer_instructions"] += self.process_metrics_line(line, "elements_i1_128")
            self.data["integer_instructions"] += self.process_metrics_line(line, "elements_i8_16")
            self.data["integer_instructions"] += self.process_metrics_line(line, "elements_i32_1")
            self.data["integer_instructions"] += self.process_metrics_line(line, "elements_i32_4")
            self.data["integer_instructions"] += self.process_metrics_line(line, "elements_i128_1")'''

            self.data["integer_instructions"] += self.process_metrics_line(line, "isa-ext-BASE")
            self.data["float_instructions"] += self.process_metrics_line(line, "isa-ext-BASE")

        print "int: " + str(self.data["integer_instructions"]) + "\n"
        print "flt: " + str(self.data["float_instructions"]) + "\n"
        print "mem: " + str(self.data["bytes_requested"]) + "\n"
        profiling_file.close()

    def parse_prog_output(self, file_name):
        profiling_file = open(file_name, 'r')
        found_final_table = False
        for line in profiling_file:
            if "ROOFLINE TIME:" in line:
                self.total_execution_time = float(line.split(" ")[2])

        profiling_file.close()

    def collect_instructions_count(self, application):
        print "measuring metrics"
        sde_command = self.get_sde_command(application)

        # measure all required metrics
        program_output = open(profiling_data_path + '/sde.txt', 'w')
        cmd = Popen(sde_command, shell=True, stdout=program_output)
        cmd.wait()
        self.parse_sde_output("./tmp/sde.out")

    def collect_execution_time(self, application):
        print "measuring time " + exec_data_path + application
        program_output = open(profiling_data_path + '/sde.txt', 'w')
        cmd = Popen(exec_data_path + application, shell=True, stdout=program_output)
        cmd.wait()
        self.parse_prog_output("./tmp/sde.txt")

    def collect_data(self, profiling_command):
        self.collect_instructions_count(profiling_command["application"])
        self.collect_execution_time(profiling_command["application"])


def profile_application(profiling_command, arch):
    profiler = ProfilingDataIntel(profiling_command['name'], arch)
    profiler.collect_data(profiling_command)

    print profiler.data

    return {"name": profiling_command["name"],
            "ops_per_byte": profiler.get_ops_per_byte(),
            "ops": profiler.get_ops()
    }


def save_profiling_data_to_file(file_name, profiling_data_array):
    file = open(file_name, "w")

    for profiling_data in profiling_data_array:
        file.write(profiling_data["name"] + "|" + str(profiling_data["ops_per_byte"]) + "|" + str(float(profiling_data["ops"]) / (pow(10.0, 9))) + "\n")

    file.close()


def run_intel_analysis(input_file_name, output_file_name, arch):
    profiling_cmd = read_cmd_file(input_file_name)

    profiling_data_array = []

    pos = 0
    for cmd in profiling_cmd:
        profiling_data_array.append(profile_application(cmd, arch))
        pos += 1

    save_profiling_data_to_file(profiling_data_path + output_file_name, profiling_data_array)
