import subprocess


def list_files(directory):
    out = subprocess.check_output("ls " + directory, shell=True, text=True)
    return sorted(out.split())
