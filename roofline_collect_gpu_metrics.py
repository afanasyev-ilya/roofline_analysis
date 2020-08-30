#!/usr/bin/python

from subprocess import Popen, PIPE, call
import re
import os
import sys, getopt

import argparse
from src.paths import *
from src.clean_data import clean_all

metrics_file_name = "metrics_file.log"
execution_times_file_name = "execution_time_file.log"

def p2f(x):
    return float(x.strip('%'))/100


class ProfilingDataGPU:
    def __init__(self, name, mode, kernel_name, find_approximate_name):
        self.data = {"gld_transactions": 0,
                     "gst_transactions": 0,
                     "atomic_transactions": 0,
                     "local_load_transactions": 0,
                     "local_store_transactions": 0,
                     "shared_load_transactions": 0,
                     "shared_store_transactions": 0,
                     "l2_read_transactions": 0,
                     "l2_write_transactions": 0,
                     "dram_read_transactions": 0,
                     "dram_write_transactions": 0,
                     "flop_count_dp": 0,
                     "flop_count_dp_fma": 0,
                     "flop_count_dp_add": 0,
                     "flop_count_dp_mul": 0,
                     "flop_count_sp": 0,
                     "flop_count_sp_fma": 0,
                     "flop_count_sp_add": 0,
                     "flop_count_sp_mul": 0,
                     "inst_integer": 0,
                     "gst_efficiency": 0,
                     "gld_efficiency": 0,
                     "shared_efficiency": 0}
        self.total_execution_time = 0.0
        self.name = name
        self.mode = mode
        self.kernel_name = kernel_name
        self.find_approximate_name = find_approximate_name

    def extract_time(self, time_str):
        print time_str
        m = re.search(r'ms$', time_str)
        if m is not None:
            self.total_execution_time += float(time_str[:-2]) / 1000.0
            return
        m = re.search(r'us$', time_str)
        if m is not None:
            self.total_execution_time += float(time_str[:-2]) / (1000.0 * 1000.0)
            return
        m = re.search(r's$', time_str)
        if m is not None:
            self.total_execution_time += float(time_str[:-1])

    def parse_metrics_file(self, file_name):
        profiling_file = open(file_name, 'r')

        active = False
        for line in profiling_file:
            if "Kernel: " in line:
                if self.get_name_to_find_in_metrics_file() in line:
                    print "found " + self.get_name_to_find_in_metrics_file() + " in line : " + line
                    active = True
                else:
                    active = False
            if active:
                print "processing line " + line
                self.process_metrics_line(line)
        profiling_file.close()

    def parse_execution_time_file(self, file_name):
        profiling_file = open(file_name, 'r')
        for line in profiling_file:
            self.process_execution_time_line(line)
        profiling_file.close()

    def process_metrics_line(self, line):
        for key in self.data:
            if str(key) in line:
                kernels_count = int(line.split()[0])
                if "efficiency" in line:
                    metric_value = float(p2f(line.split()[-1]))
                else:
                    metric_value = float(line.split()[-1])
                self.data[key] += kernels_count * metric_value

    def process_execution_time_line(self, line):
        if self.get_name_to_find_in_execution_time_file() in line:
            print "found " + self.get_name_to_find_in_execution_time_file() + " in line : " + line
            if "GPU activities" in line:
                self.extract_time(line.split()[3])
            else:
                self.extract_time(line.split()[1])
            return

    def get_name_to_find_in_execution_time_file(self):
        if self.find_approximate_name is True:
            return self.kernel_name
        else:
            return " " + self.kernel_name + "("

    def get_name_to_find_in_metrics_file(self):
        if self.find_approximate_name is True:
            return self.kernel_name
        else:
            return "Kernel: " + self.kernel_name + "("

    def get_metric_names(self):
        metric_list = []
        for key in self.data:
            metric_list.append(key)
        return ",".join(metric_list)

    def get_bytes_requested_l1(self):
        bytes_requested = 32 * (self.data["gld_transactions"] + self.data["gst_transactions"] +
                                self.data["local_load_transactions"] + self.data["local_store_transactions"] +
                                self.data["shared_load_transactions"] + self.data["shared_store_transactions"] +
                                self.data["atomic_transactions"])
        return bytes_requested

    def get_bytes_requested_l2(self):
        bytes_requested = 32 * (self.data["l2_read_transactions"] + self.data["l2_write_transactions"])
        return bytes_requested

    def get_bytes_requested_dram(self):
        bytes_requested = 32 * (self.data["dram_read_transactions"] + self.data["dram_write_transactions"])
        return bytes_requested

    def get_bytes_requested_program(self):
        bytes_requested = 0
        bytes_requested += 32 * self.data["gld_transactions"] * self.data["gld_efficiency"]
        bytes_requested += 32 * self.data["gst_transactions"] * self.data["gst_efficiency"]
        bytes_requested += 32 * (self.data["shared_load_transactions"] + self.data["shared_store_transactions"]) * self.data["shared_efficiency"]
        return bytes_requested

    def get_L1_hit_rate_program(self):
        total_accesses = float(32 * (self.data["gld_transactions"] + self.data["gst_transactions"]))
        misses = float(32 * (self.data["l2_read_transactions"] + self.data["l2_write_transactions"]))
        hits = total_accesses - misses
        L1_hit_rate = 100.0 * hits / total_accesses
        return L1_hit_rate

    def get_L2_hit_rate_program(self):
        total_accesses = float(32 * (self.data["l2_read_transactions"] + self.data["l2_write_transactions"]))
        misses = float(32 * (self.data["dram_read_transactions"] + self.data["dram_read_transactions"]))
        hits = total_accesses - misses
        L2_hit_rate = 100.0 * hits / total_accesses
        return L2_hit_rate

    def get_total_ops(self):
        if self.mode == "int":
            return self.data["inst_integer"]
        if self.mode == "sp":
            return self.data["flop_count_sp"]
        if self.mode == "dp":
            return self.data["flop_count_dp"]

    def get_ops_per_second(self):
        return float(self.get_total_ops()) / float(self.total_execution_time)

    def get_name(self):
        return self.name

    def get_kernel_name(self):
        return self.kernel_name

    def save_to_file(self, file):
        ops_per_second = float(self.get_ops_per_second())
        l1_AI = float(self.get_total_ops()) / float(self.get_bytes_requested_l1())
        l2_AI = float(self.get_total_ops()) / float(self.get_bytes_requested_l2())
        dram_AI = float(self.get_total_ops()) / float(self.get_bytes_requested_dram())
        program_AI = float(self.get_total_ops()) / float(self.get_bytes_requested_program())
        ops_per_second /= float(10**9)
        file.write("%s (L1), hit rate %f |%f|%f|L1|fma\n" % (self.kernel_name, self.get_L1_hit_rate_program(), ops_per_second, l1_AI))
        file.write("%s (L2), hit rate %f |%f|%f|L2|fma\n" % (self.kernel_name, self.get_L2_hit_rate_program(), ops_per_second, l2_AI))
        file.write("%s (DRAM)|%f|%f|DRAM|fma\n" % (self.kernel_name, ops_per_second, dram_AI))
        file.write("%s (program)|%f|%f|L1|fma\n" % (self.kernel_name, ops_per_second, program_AI))
        file.write("# L1 hit rate: %f\n" % self.get_L1_hit_rate_program())
        file.write("# L2 hit rate: %f\n" % self.get_L2_hit_rate_program())


def get_nvprof_metric_command(application, application_params, kernel_name, metric_names):
    nvprof_args = nvprof_path
    nvprof_args += " --log-file " + profiling_data_path + "/" + application + "_" + metrics_file_name
    nvprof_args += " --kernels " + kernel_name + " "
    nvprof_args += " --metrics "
    nvprof_args += " " + metric_names + " "
    nvprof_args += exec_data_path + application
    for param in application_params:
        nvprof_args += " " + param
    print nvprof_args
    return nvprof_args


def get_nvprof_execution_time_command(application, application_params):
    nvprof_args = nvprof_path
    nvprof_args += " --log-file " + profiling_data_path + "/" + application + "_" + execution_times_file_name + " "
    nvprof_args += exec_data_path + application
    for param in application_params:
        nvprof_args += " " + param
    print nvprof_args
    return nvprof_args


def profile_application(application, application_params, kernel, mode, find_approximate_name):

    profiling_data = ProfilingDataGPU(application, mode, kernel, find_approximate_name)

    if not os.path.isfile(exec_data_path + application):
        raise ValueError("ERROR: application not found, aborting...")

    nvprof_collect_metric_command = get_nvprof_metric_command(application, application_params, kernel,
                                                              profiling_data.get_metric_names())
    nvprof_measure_time_command = get_nvprof_execution_time_command(application, application_params)

    # measure all required metrics
    program_output = open(profiling_data_path + '/program_output.txt', 'w')
    cmd = Popen(nvprof_collect_metric_command, shell=True, stdout=program_output)
    cmd.wait()

    # measure execution time
    cmd = Popen(nvprof_measure_time_command, shell=True, stdout=program_output)
    cmd.wait()
    program_output.close()

    profiling_data.parse_metrics_file(profiling_data_path + "/" + application + "_" + metrics_file_name)
    profiling_data.parse_execution_time_file(profiling_data_path + "/" + application + "_" + execution_times_file_name)

    print profiling_data.data
    print str(profiling_data.total_execution_time) + " sec"

    return profiling_data


def main():
    parser = argparse.ArgumentParser(description='Collects data of GPU application for further roofline analysis.')

    parser.add_argument('-m', '--mode',
                        action="store", dest="mode",
                        help="Set precision mode. \"DP\" for double precision, \"SP\" for single precision, \"int\" for integer based roofline",
                        required=True)

    parser.add_argument('-k', '--kernels',
                        action="store", dest="kernels",
                        help="All kernel names, metrics about which should be collected.")

    parser.add_argument('-f', '--metric-file',
                        action="store", dest="metric_file",
                        help="Save information about collected metrics into a separate file with a specified name.",
                        default="none")

    parser.add_argument('-t', '--target-app',
                        action="store", dest="target_app",
                        help="Specify a name of application, which should be profiled.",
                        required=True)

    parser.add_argument('-l', '--list', nargs='+', action="store", dest="app_params", help='Specify additional arguments, required for the profiled application')

    args = parser.parse_args()

    if not os.path.exists(profiling_data_path):
        os.makedirs(profiling_data_path)

    try:
        kernels_list = words = args.kernels.split(",")
        if args.app_params is None:
            args.app_params = []

        result_file = open(args.target_app + "_profiling_results.txt", "w")
        result_file.write("APP: %s " % args.target_app)

        for app_arg in args.app_params:
            result_file.write(" %s " % app_arg)
        result_file.write("\n")
        result_file.write("MODE: %s\n" % args.mode)

        kernel_pos = 1
        for kernel_name in kernels_list:
            find_approximate_name = False
            if "*" in kernel_name:
                find_approximate_name = True
                kernel_name = kernel_name.replace("*", "")
            result_file.write("KERNEL %d: %s \n" % (kernel_pos, kernel_name))
            profiling_data = profile_application(args.target_app, args.app_params, kernel_name, args.mode,
                                                 find_approximate_name)
            kernel_pos += 1

            profiling_data.save_to_file(result_file)

        result_file.close()

    except Exception as e:
        print str(e)
        #clean_all()
        exit()

if __name__ == "__main__":
    main()
