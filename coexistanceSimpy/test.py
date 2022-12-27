import os

import pandas as pd
import matplotlib.pyplot as plt
from decimal import Decimal

path_prefix = "/folder22323"
db_fbe_df_no_offset = pd.read_csv(os.getcwd() + path_prefix + "/db_fbe_df_no_offset.csv", sep=',').sort_values(by="cot")
fixed_muting_fbe_df_with_offset = pd.read_csv(os.getcwd() + path_prefix + "/fixed_muting_fbe_df_no_offset.csv",
                                              sep=',').sort_values(by="cot")
floating_fbe_df_no_offset = pd.read_csv(os.getcwd() + path_prefix + "/floating_fbe_df_with_offset.csv",
                                        sep=',').sort_values(by="cot")
random_muting_fbe_df_with_offset = pd.read_csv(os.getcwd() + path_prefix + "/random_muting_fbe_df_with_offset.csv",
                                               sep=',').sort_values(by="cot")


def plot_bars(bar_names, bar_values, colors, file_name, title):
    plt.bar(bar_names, bar_values, color=colors, width=0.8, align='center')
    plt.ylim([0, 1])
    plt.ylabel(title)
    plt.savefig(file_name)
    plt.close()


def calculate_norm_summ_airtime(df, sim_time=1000000):
    return Decimal(df.get("summary_air_time").tolist()[-1]) / Decimal(sim_time)


# plot_bars(["Floating FBE", "Deterministic-backoff FBE"],
#           [calculate_norm_summ_airtime(floating_fbe_df_no_offset), calculate_norm_summ_airtime(db_fbe_df_no_offset)], ['c', 'g'])
plot_bars(["Fixed-muting FBE", "Random-muting FBE"],
          [calculate_norm_summ_airtime(fixed_muting_fbe_df_with_offset),
           calculate_norm_summ_airtime(random_muting_fbe_df_with_offset)],
          ['c', 'g'],
          'fm_rm_summ_with_offset.svg',
          "Normalized summary airtime")

plot_bars(["Floating FBE", "Deterministic-backoff FBE"],
          [calculate_norm_summ_airtime(floating_fbe_df_no_offset),
           calculate_norm_summ_airtime(db_fbe_df_no_offset)],
          ['m', 'b'],
          'floating_db_norm_no_offset.svg',
          "Normalized summary airtime")

plot_bars(["Fixed-muting FBE", "Random-muting FBE"],
          [fixed_muting_fbe_df_with_offset.get("fairness").tolist()[-1],
           random_muting_fbe_df_with_offset.get("fairness").tolist()[-1]],
          ['c', 'g'],
          'fm_rm_fairness_with_offset.svg',
          "Fairness")

plot_bars(["Floating FBE", "Deterministic-backoff FBE"],
          [floating_fbe_df_no_offset.get("fairness").tolist()[-1],
           db_fbe_df_no_offset.get("fairness").tolist()[-1]],
          ['m', 'b'],
          'floating_db_fairness_no_offset.svg',
          "Fairness")
