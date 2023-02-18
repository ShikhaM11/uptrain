import numpy as np
import copy

from uptrain.core.lib.helper_funcs import extract_data_points_from_batch
from uptrain.core.classes.distances import DistanceResolver
from uptrain.core.classes.statistics import AbstractStatistic
from uptrain.core.classes.measurables import MeasurableResolver
from uptrain.constants import Statistic
from uptrain.core.classes.algorithms import Clustering
from uptrain.core.lib.algorithms import estimate_earth_moving_cost

class Convergence(AbstractStatistic):
    dashboard_name = "convergence_stats"
    anomaly_type = Statistic.CONVERGENCE_STATS

    def __init__(self, fw, check):
        self.allowed_model_values = [x['allowed_values'] for x in check['model_args']]
        self.num_model_options = sum([len(x) > 1 for x in self.allowed_model_values])
        self.children = []

        if self.num_model_options > 0:
            for m in self.allowed_model_values[0]:
                check_copy = copy.deepcopy(check)
                check_copy['model_args'][0]['allowed_values'] = [m]
                check_copy['model_args'].append(copy.deepcopy(check_copy['model_args'][0]))
                del check_copy['model_args'][0]
                self.children.append(Convergence(fw, check_copy))
        else:
            self.log_handler = fw.log_handler
            self.measurable = MeasurableResolver(check["measurable_args"]).resolve(fw)
            self.aggregate_measurable = MeasurableResolver(check["aggregate_args"]).resolve(
                fw
            )
            self.count_measurable = MeasurableResolver(check["count_args"]).resolve(
                fw
            )
            self.feature_measurables = [
                MeasurableResolver(x).resolve(fw) for x in check["feature_args"]
            ]
            self.model_measurables = [
                MeasurableResolver(x).resolve(fw) for x in check["model_args"]
            ]
            self.model_names = [x.col_name() for x in self.model_measurables]
            self.feature_names = [x.col_name() for x in self.feature_measurables]
            self.item_counts = {}
            self.first_count_checkpoint = {}
            self.reference = check["reference"]
            self.distance_types = check["distance_types"]

            self.count_checkpoints = np.unique(np.array([0] + check["count_checkpoints"]))

            self.feats_dictn = dict(zip(list(self.count_checkpoints), [{} for x in list(self.count_checkpoints)]))
            # ex: {0: {agg_id_0: val_0, ..}, 200: {}, 500: {}, 1000: {}, 5000: {}, 20000: {}}

            self.distances_dictn = dict(zip(list(self.count_checkpoints), [dict(zip(self.distance_types, [[] for x in list(self.distance_types)])) for y in list(self.count_checkpoints)]))
            #ex: {0: {'cosine_distance': [d1, d2, ..]}, 200: {'cosine_distance': []}, 500: {'cosine_distance': []}, 1000: {'cosine_distance': []}, 5000: {'cosine_distance': []}, 20000: {'cosine_distance': []}}

            self.dist_classes = [DistanceResolver().resolve(x) for x in self.distance_types]
            self.total_count = 0
            self.prev_calc_at = 0

    def check(self, inputs, outputs, gts=None, extra_args={}):
        if len(self.children) > 0:
            [x.check(inputs, outputs, gts, extra_args) for x in self.children]
        else:
            vals = self.measurable.compute_and_log(
                inputs, outputs, gts=gts, extra=extra_args
            )
            aggregate_ids = self.aggregate_measurable.compute_and_log(
                inputs, outputs, gts=gts, extra=extra_args
            )
            counts = self.count_measurable.compute_and_log(
                inputs, outputs, gts=gts, extra=extra_args
            )
            all_models = [x.compute_and_log(
                inputs, outputs, gts=gts, extra=extra_args
            ) for x in self.model_measurables]
            all_features = [x.compute_and_log(
                inputs, outputs, gts=gts, extra=extra_args
            ) for x in self.feature_measurables]
            update_counts = []
            self.total_count += len(extra_args['id'])

            models = dict(zip(['model_' + x for x in self.model_names], [self.allowed_model_values[jdx][0] for jdx in range(len(self.model_names))]))

            for idx in range(len(aggregate_ids)):
                is_model_invalid = sum([all_models[jdx][idx] not in self.allowed_model_values[jdx] for jdx in range(len(self.allowed_model_values))])
                if is_model_invalid:
                    continue

                if aggregate_ids[idx] not in self.item_counts:
                    self.item_counts.update({aggregate_ids[idx]: 0})

                this_item_count_prev = self.item_counts[aggregate_ids[idx]]
                if this_item_count_prev == counts[idx]:
                    continue
                self.item_counts[aggregate_ids[idx]] = counts[idx]
                this_item_count = self.item_counts[aggregate_ids[idx]]

                crossed_checkpoint_arr = (np.logical_xor((self.count_checkpoints > this_item_count), (self.count_checkpoints > this_item_count_prev)))
                has_crossed_checkpoint = sum(crossed_checkpoint_arr)

                if has_crossed_checkpoint:
                    crossed_checkpoint = self.count_checkpoints[np.where(crossed_checkpoint_arr == True)[0][-1]]

                    if aggregate_ids[idx] not in self.first_count_checkpoint:
                        self.first_count_checkpoint.update({aggregate_ids[idx]: crossed_checkpoint})

                    this_val = extract_data_points_from_batch(vals, [idx])

                    self.feats_dictn[crossed_checkpoint].update({aggregate_ids[idx]: this_val})
                    if crossed_checkpoint > self.first_count_checkpoint[aggregate_ids[idx]]:
                        if self.reference == "running_diff":
                            this_count_idx = np.where(self.count_checkpoints == crossed_checkpoint)[0][0]
                            prev_count_idx = max(0, this_count_idx - 1)
                            found_ref = False
                            while not found_ref:
                                ref_item_count = self.count_checkpoints[prev_count_idx]
                                if aggregate_ids[idx] in self.feats_dictn[ref_item_count]:
                                    break
                                prev_count_idx = max(0, prev_count_idx - 1)
                        else:
                            ref_item_count = self.first_count_checkpoint[aggregate_ids[idx]]
                        this_distances = dict(
                            zip(
                                self.distance_types,
                                [
                                    x.compute_distance(
                                        this_val,
                                        self.feats_dictn[ref_item_count][
                                            aggregate_ids[idx]
                                        ],
                                    )
                                    for x in self.dist_classes
                                ],
                            )
                        )
                        update_counts.append(crossed_checkpoint)
                        if self.reference == "running_diff":
                            del self.feats_dictn[ref_item_count][aggregate_ids[idx]]
                        else:
                            del self.feats_dictn[crossed_checkpoint][aggregate_ids[idx]]

                        features = dict(zip(['feature_' + x for x in self.feature_names], [all_features[jdx][idx] for jdx in range(len(self.feature_names))]))

                        for distance_key in list(this_distances.keys()):
                            plot_name = (
                                distance_key
                                + " "
                                + str(self.reference)
                            )
                            this_data = list(np.reshape(np.array(this_distances[distance_key]),-1))

                            self.distances_dictn[crossed_checkpoint][distance_key].extend(
                                this_data
                            )

                            self.log_handler.add_histogram(
                                plot_name,
                                this_data,
                                self.dashboard_name,
                                count = crossed_checkpoint,
                                models = [models]*len(this_data),
                                features = [features] * len(this_data),
                                file_name = str(crossed_checkpoint)
                            )


            # print(self.allowed_model_values)
            # if self.allowed_model_values == [['realtime'], ['unified']]:
            #     import pdb; pdb.set_trace()
            if ((self.total_count - self.prev_calc_at) > 50000):
                self.prev_calc_at = self.total_count
                for count in list(self.distances_dictn.keys()):
                    if (count > 0): # and (count in update_counts):
                        for distance_type in self.distance_types:
                            plot_name = (
                                distance_type
                                + " "
                                + str(self.reference)
                                # + self.measurable.col_name()
                                # + " "
                                # + self.aggregate_measurable.col_name()
                            )
                            this_data = np.reshape(
                                    np.array(self.distances_dictn[count][distance_type]), -1
                                )

                            if len(this_data) > 5:
                                self.log_handler.add_scalars(
                                    plot_name + "_mean",
                                    {'y_mean': np.mean(this_data)},
                                    count,
                                    # self.total_count,                     
                                    self.dashboard_name,
                                    models = models,
                                    file_name = str("count"),
                                    update_val = True
                                )
                                self.log_handler.add_scalars(
                                    plot_name + "_std",
                                    {'y_std': np.std(this_data)},
                                    count,
                                    # self.total_count,                     
                                    self.dashboard_name,
                                    models = models,
                                    file_name = str("count"),
                                    update_val = True
                                )

                                next_count_idx = np.where(self.count_checkpoints == (count))[0][0] + 1
                                if next_count_idx < len(self.count_checkpoints):
                                    next_data = np.reshape(
                                        np.array(self.distances_dictn[self.count_checkpoints[next_count_idx]][distance_type]), -1
                                    )
                                    if len(next_data) > 5:
                                        clustering_helper = Clustering({"num_buckets": 2, "is_embedding": False})
                                        this_data = np.expand_dims(np.array(this_data), axis=(1))
                                        next_data = np.expand_dims(np.array(next_data), axis=(1,2))
                                        this_count_clustering_res = clustering_helper.cluster_data(this_data)
                                        next_count_clustering_res = clustering_helper.infer_cluster_assignment(next_data)
                                        emd_cost = estimate_earth_moving_cost(np.reshape(next_count_clustering_res[1]/next_data.shape[0],-1), np.reshape(clustering_helper.dist[0],-1), clustering_helper.clusters[0])
                                        self.log_handler.add_scalars(
                                            plot_name + "_emd",
                                            {'y_distance': emd_cost},
                                            count,
                                            # self.total_count,                     
                                            self.dashboard_name,
                                            models = models,
                                            file_name = str("count"),
                                            update_val = True
                                        )

                                    
