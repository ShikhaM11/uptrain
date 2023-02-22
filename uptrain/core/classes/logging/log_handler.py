import os
import shutil

class LogHandler:
    def __init__(self, framework=None, cfg=None):
        self.fw = framework
        if os.path.exists(cfg.log_folder):
            print("Deleting the folder: ", cfg.log_folder)
            shutil.rmtree(cfg.log_folder)

        self.st_writer = None
        if cfg.st_logging:
            from uptrain.core.classes.logging.log_streamlit import StreamlitLogs

            self.st_log_folder = os.path.join(cfg.log_folder, "st_data")
            os.makedirs(self.st_log_folder, exist_ok=True)
            self.st_writer = StreamlitLogs(self.st_log_folder)

    def add_writer(self, dashboard_name):
        dashboard_name = self.dir_friendly_name(dashboard_name)
        tb_writer = None
        if self.tb_logs:
            tb_writer = self.tb_logs.add_writer(dashboard_name)
            self.tb_writers.update({dashboard_name: tb_writer})

    def get_plot_save_name(self, plot_name, dashboard_name):
        if self.st_writer:
            return os.path.join(self.st_log_folder, dashboard_name, plot_name)
        else:
            return ""

    def add_scalars(self, plot_name, dictn, count, dashboard_name, features={}, models={}, file_name='', update_val=False):
        if self.st_writer is None:
            return
        dashboard_name, plot_name = self.dir_friendly_name(
            [dashboard_name, plot_name]
        )
        dictn.update(features)
        dictn.update(models)
        new_dictn = dict(
            zip(
                self.dir_friendly_name(list(dictn.keys())),
                dictn.values(),
            )
        )
        dashboard_dir = os.path.join(self.st_log_folder, dashboard_name)
        plot_folder = os.path.join(dashboard_dir, "line_plots", plot_name)
        os.makedirs(plot_folder, exist_ok=True)
        new_dictn.update({"x_count": count})
        self.st_writer.add_scalars(new_dictn, plot_folder, file_name=file_name, update_val=update_val)

    def add_histogram(self, plot_name, data, dashboard_name, count=-1, features=None, models=None, file_name=""):
        dashboard_name, plot_name = self.dir_friendly_name(
            [dashboard_name, plot_name]
        )
        if self.st_writer:
            dashboard_dir = os.path.join(self.st_log_folder, dashboard_name)
            plot_folder = os.path.join(dashboard_dir, "histograms", plot_name)
            os.makedirs(plot_folder, exist_ok=True)
            self.st_writer.add_histogram(data, plot_folder, features=features, models=models, file_name=file_name)

    def add_alert(self, alert_name, alert, dashboard_name):
        if self.st_writer is None:
            return
        dashboard_name = self.dir_friendly_name(dashboard_name)
        dashboard_dir = os.path.join(self.st_log_folder, dashboard_name)
        plot_folder = os.path.join(dashboard_dir, "alerts")
        os.makedirs(plot_folder, exist_ok=True)
        self.st_writer.add_alert(alert_name, alert, plot_folder)

    def add_bar_graphs(self, plot_name, data, dashboard_name, count=-1):
        if self.st_writer is None:
            return
        dashboard_name, plot_name = self.dir_friendly_name(
            [dashboard_name, plot_name]
        )
        dashboard_dir = os.path.join(self.st_log_folder, dashboard_name)
        plot_folder = os.path.join(dashboard_dir, "bar_graphs", plot_name)
        os.makedirs(plot_folder, exist_ok=True)
        self.st_writer.add_bar_graphs(data, plot_folder, count)

    def dir_friendly_name(self, arr):
        if isinstance(arr, str):
            return self.dir_friendly_name([arr])[0]

        new_arr = [self.convert_str(x) for x in arr]
        return new_arr

    def convert_str(self, txt):
        txt = txt.replace("(", "_")
        txt = txt.replace(")", "_")
        txt = txt.replace(":", "_")
        txt = txt.replace(" ", "_")
        txt = txt.replace(",", "_")
        txt = txt.replace(">", "_")
        txt = txt.replace("<", "_")
        txt = txt.replace("=", "_")
        txt = txt.replace("-", "_")
        return txt
