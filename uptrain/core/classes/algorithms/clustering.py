import numpy as np
from uptrain.core.lib.helper_funcs import cluster_and_plot_data

class Clustering():
    def __init__(self, args) -> None:
        self.NUM_BUCKETS = args["num_buckets"]
        self.is_embedding = args["is_embedding"]
        self.plot_save_name = args.get("plot_save_name", "")
        self.dist = []
        self.dist_counts = []


    def cluster_data(self, data):
        if self.is_embedding:
            self.bucket_vector(data, plot_save_name=self.plot_save_name)
        else:
            buckets = []
            clusters = []
            cluster_vars = []
            for idx in range(data.shape[1]):
                this_inputs = data[:, idx]
                this_buckets, this_clusters, this_cluster_vars = self.bucket_scalar(
                    this_inputs
                )
                buckets.append(this_buckets)
                clusters.append(this_clusters)
                cluster_vars.append(this_cluster_vars)
            self.buckets = np.array(buckets)
            self.clusters = np.array(clusters)
            self.cluster_vars = np.array(cluster_vars)

        self.dist = np.array(self.dist)
        self.dist_counts = np.array(self.dist_counts)

        clustering_results = {
            "buckets": self.buckets,
            "clusters": self.clusters,
            "cluster_vars": self.cluster_vars,
            "dist": self.dist,
            "dist_counts": self.dist_counts
        }

        return clustering_results


    def bucket_scalar(self, arr):
        sorted_arr = np.sort(arr)
        buckets = []
        clusters = []
        cluster_vars = []
        for idx in range(0, self.NUM_BUCKETS):
            if idx > 0:
                buckets.append(
                    sorted_arr[int(idx * (len(sorted_arr) - 1) / self.NUM_BUCKETS)]
                )
            this_bucket_elems = sorted_arr[
                int((idx) * (len(sorted_arr) - 1) / self.NUM_BUCKETS) : int(
                    (idx + 1) * (len(sorted_arr) - 1) / self.NUM_BUCKETS
                )
            ]
            gaussian_mean = np.mean(this_bucket_elems)
            gaussian_var = np.var(this_bucket_elems)
            clusters.append([gaussian_mean])
            cluster_vars.append([gaussian_var])

        self.dist.append([[1 / self.NUM_BUCKETS] for x in range(self.NUM_BUCKETS)])
        self.dist_counts.append(
            [[int(len(sorted_arr) / self.NUM_BUCKETS)] for x in range(self.NUM_BUCKETS)]
        )
        return np.array(buckets), np.array(clusters), np.array(cluster_vars)

    def bucket_vector(self, data, plot_save_name=''):

        all_clusters, counts, cluster_vars = cluster_and_plot_data(
            data,
            self.NUM_BUCKETS,
            cluster_plot_func=self.cluster_plot_func,
            plot_save_name=plot_save_name,
        )

        self.clusters = np.array([all_clusters])
        self.cluster_vars = np.array([cluster_vars])

        self.dist_counts = np.array([counts])
        self.dist = self.dist_counts / data.shape[0]

    def infer_cluster_assignment(self, feats, prod_dist_counts=None):
        if prod_dist_counts is None:
            prod_dist_counts = np.zeros((feats.shape[1], self.NUM_BUCKETS))
        if self.is_embedding:
            selected_cluster = np.argmin(
                np.sum(
                    np.abs(self.clusters[0] - feats),
                    axis=tuple(range(2, len(feats.shape))),
                ),
                axis=1,
            )
            for clus in selected_cluster:
                prod_dist_counts[0][clus] += 1
            this_datapoint_cluster = selected_cluster
        else:
            this_datapoint_cluster = []
            for idx in range(feats.shape[1]):
                bucket_idx = np.searchsorted(
                    self.buckets[idx], feats[:, :, idx]
                )[:, 0]
                this_datapoint_cluster.append(bucket_idx)
                for clus in bucket_idx:
                    prod_dist_counts[idx][clus] += 1
            this_datapoint_cluster = np.array(this_datapoint_cluster)
        return this_datapoint_cluster, prod_dist_counts