Run
import os
    subprocess.check_call([
        "python", "-m", "pip", "install", "psutil"
    ])
    import psutil




def format_bytes(size):
    """Convert bytes into GB."""
    return round(size / (1024 ** 3), 2)




def check_system_usage():
    print("=" * 40)
    print("       SYSTEM RESOURCE MONITOR")
    print("=" * 40)


    while True:
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()


            os.system("cls" if os.name == "nt" else "clear")


            print("=" * 40)
            print("       SYSTEM RESOURCE MONITOR")
            print("=" * 40)


            print(f"\nCPU Usage: {cpu_usage}%")
            print(f"CPU Cores: {psutil.cpu_count(logical=True)}")


            print("\nMEMORY INFORMATION")
            print(f"Total RAM:     {format_bytes(memory.total)} GB")
            print(f"Used RAM:      {format_bytes(memory.used)} GB")
            print(f"Available RAM: {format_bytes(memory.available)} GB")
            print(f"RAM Usage:     {memory.percent}%")


            print("\n" + "=" * 40)


            if cpu_usage > 90:
                print("WARNING: High CPU usage!")


            if memory.percent > 90:
                print("WARNING: High memory usage!")


            print("\nPress Ctrl+C to exit.")
            time.sleep(1)


        except KeyboardInterrupt:
            print("\nSystem monitor stopped.")
            break




if __name__ == "__main__":
    check_system_usage()