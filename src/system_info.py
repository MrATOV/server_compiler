import psutil
import cpuinfo
import subprocess
import platform

def get_compiler_info():
    try:
        result = subprocess.run(['gcc', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            compiler_info = result.stdout.split('\n')[0].split()
            return f"{compiler_info[0].upper()} {compiler_info[1]} {compiler_info[2]} {compiler_info[3]}"
    except FileNotFoundError:
        pass
    return "Неизвестно"


def get_system_info():
    cpu_info = cpuinfo.get_cpu_info()
    processor_name = cpu_info.get('brand_raw', 'Неизвестно')

    physical_cores = psutil.cpu_count(logical=False) or 1

    return {
        'processor_name': processor_name,
        'physical_cores': physical_cores,
        'compiler': get_compiler_info(),
        'language_version': 'C++17'
    }