#
# Copyright 2018 Analytics Zoo Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from zoo.orca.data.utils import row_to_sample, xshard_to_sample
from zoo.orca.learn.utils import convert_predict_rdd_to_dataframe
from zoo.pipeline.estimator.estimator import Estimator as SparkEstimator
from zoo.orca.learn.ray_estimator import Estimator as OrcaRayEstimator
from zoo.orca.learn.pytorch.training_operator import TrainingOperator
from zoo.orca.learn.spark_estimator import Estimator as OrcaSparkEstimator
from zoo.orca.learn.optimizers import Optimizer as OrcaOptimizer, SGD
from zoo.orca.data import SparkXShards
from bigdl.optim.optimizer import MaxEpoch, OptimMethod
from zoo.feature.common import FeatureSet
from torch.optim.optimizer import Optimizer as TorchOptimizer
from torch.utils.data import DataLoader
from pyspark.sql import DataFrame


class Estimator(object):
    @staticmethod
    def from_torch(*,
                   model,
                   optimizer,
                   loss=None,
                   scheduler_creator=None,
                   training_operator_cls=TrainingOperator,
                   initialization_hook=None,
                   config=None,
                   scheduler_step_freq="batch",
                   use_tqdm=False,
                   workers_per_node=1,
                   model_dir=None,
                   backend="bigdl"):
        if backend in {"horovod", "torch_distributed"}:
            return PyTorchRayEstimator(model_creator=model,
                                       optimizer_creator=optimizer,
                                       loss_creator=loss,
                                       scheduler_creator=scheduler_creator,
                                       training_operator_cls=training_operator_cls,
                                       initialization_hook=initialization_hook,
                                       config=config,
                                       scheduler_step_freq=scheduler_step_freq,
                                       use_tqdm=use_tqdm,
                                       workers_per_node=workers_per_node,
                                       backend=backend)
        elif backend == "bigdl":
            return PyTorchSparkEstimator(model=model,
                                         loss=loss,
                                         optimizer=optimizer,
                                         model_dir=model_dir,
                                         bigdl_type="float")
        else:
            raise ValueError("Only horovod, torch_distributed and bigdl backends are supported"
                             f" for now, got backend: {backend}")


class PyTorchRayEstimator(OrcaRayEstimator):
    def __init__(self,
                 *,
                 model_creator,
                 optimizer_creator,
                 loss_creator=None,
                 scheduler_creator=None,
                 training_operator_cls=TrainingOperator,
                 initialization_hook=None,
                 config=None,
                 scheduler_step_freq="batch",
                 use_tqdm=False,
                 backend="torch_distributed",
                 workers_per_node=1):
        from zoo.orca.learn.pytorch.pytorch_ray_estimator import PyTorchRayEstimator
        self.estimator = PyTorchRayEstimator(model_creator=model_creator,
                                             optimizer_creator=optimizer_creator,
                                             loss_creator=loss_creator,
                                             scheduler_creator=scheduler_creator,
                                             training_operator_cls=training_operator_cls,
                                             initialization_hook=initialization_hook,
                                             config=config,
                                             scheduler_step_freq=scheduler_step_freq,
                                             use_tqdm=use_tqdm,
                                             backend=backend,
                                             workers_per_node=workers_per_node)

    def fit(self, data, epochs=1, batch_size=32, profile=False, reduce_results=True, info=None,
            feature_cols=None, label_cols=None):
        """
        Trains a PyTorch model given training data for several epochs.

        Calls `TrainingOperator.train_epoch()` on N parallel workers simultaneously
        underneath the hood.
        :param data: An instance of SparkXShards, a Spark DataFrame or a function that
        takes config as argument and returns a PyTorch DataLoader for training.
        :param epochs: The number of epochs to train the model. Default is 1.
        :param batch_size: The number of samples per batch for each worker. Default is 32.
        The total batch size would be workers_per_node*num_nodes.
        If you training data is a function, you can set batch_size to be config["batch_size"]
        for the PyTorch DataLoader.
        :param profile: Boolean. Whether to return time stats for the training procedure.
        Default is False.
        :param reduce_results: Boolean. Whether to average all metrics across all workers into
        one dict. If a metric is a non-numerical value (or nested dictionaries), one value will
        be randomly selected among the workers. If False, returns a list of dicts for all workers.
        Default is True.
        :param info: An optional dictionary that can be passed to the TrainingOperator for
        train_epoch and train_batch.
        :param feature_cols: feature column names if data is Spark DataFrame.
        :param label_cols: label column names if data is Spark DataFrame.

        :return A list of dictionary of metrics for every training epoch. If reduce_results is
        False, this will return a nested list of metric dictionaries whose length will be equal
        to the total number of workers.
        You can also provide custom metrics by passing in a custom training_operator_cls when
        creating the Estimator.
        """
        return self.estimator.train(data=data, epochs=epochs, batch_size=batch_size,
                                    profile=profile, reduce_results=reduce_results,
                                    info=info, feature_cols=feature_cols,
                                    label_cols=label_cols)

    def predict(self, data, batch_size=32, feature_cols=None, profile=False):
        """
        Using this PyTorch model to make predictions on the data.

        :param data: An instance of SparkXShards or a Spark DataFrame
        :param batch_size: The number of samples per batch for each worker. Default is 32.
        :param profile: Boolean. Whether to return time stats for the training procedure.
        Default is False.
        :param feature_cols: feature column names if data is a Spark DataFrame.
        :return A SparkXShards that contains the predictions with key "prediction" in each shard
        """
        return self.estimator.predict(data, batch_size=batch_size,
                                      feature_cols=feature_cols,
                                      profile=profile)

    def evaluate(self, data, batch_size=32, num_steps=None, profile=False, info=None,
                 feature_cols=None, label_cols=None):
        """
        Evaluates a PyTorch model given validation data.
        Note that only accuracy for classification with zero-based label is supported by
        default. You can override validate_batch in TrainingOperator for other metrics.

        Calls `TrainingOperator.validate()` on N parallel workers simultaneously
        underneath the hood.
        :param data: An instance of SparkXShards, a Spark DataFrame or a function that
        takes config as argument and returns a PyTorch DataLoader for validation.
        :param batch_size: The number of samples per batch for each worker. Default is 32.
        The total batch size would be workers_per_node*num_nodes.
        If you validation data is a function, you can set batch_size to be config["batch_size"]
        for the PyTorch DataLoader.
        :param num_steps: The number of batches to compute the validation results on. This
        corresponds to the number of times `TrainingOperator.validate_batch` is called.
        :param profile: Boolean. Whether to return time stats for the training procedure.
        Default is False.
        :param info: An optional dictionary that can be passed to the TrainingOperator
        for validate.
        :param feature_cols: feature column names if train data is Spark DataFrame.
        :param label_cols: label column names if train data is Spark DataFrame.

        :return A dictionary of metrics for the given data, including validation accuracy and loss.
        You can also provide custom metrics by passing in a custom training_operator_cls when
        creating the Estimator.
        """
        return self.estimator.validate(data=data, batch_size=batch_size, num_steps=num_steps,
                                       profile=profile, info=info, feature_cols=feature_cols,
                                       label_cols=label_cols)

    def get_model(self):
        """Returns the learned model(s)."""
        return self.estimator.get_model()

    def save(self, checkpoint):
        """Saves the Estimator state to the provided checkpoint path.

        :param checkpoint: (str) Path to target checkpoint file.
        """
        return self.estimator.save(checkpoint=checkpoint)

    def load(self, checkpoint):
        """Loads the Estimator and all workers from the provided checkpoint.

        :param checkpoint: (str) Path to target checkpoint file.
        """
        return self.estimator.load(checkpoint=checkpoint)

    def shutdown(self, force=False):
        """Shuts down workers and releases resources."""
        return self.estimator.shutdown(force=force)


class PyTorchSparkEstimator(OrcaSparkEstimator):
    def __init__(self, model, loss, optimizer, model_dir=None, bigdl_type="float"):
        from zoo.pipeline.api.torch import TorchModel, TorchLoss, TorchOptim
        self.loss = loss
        if self.loss is None:
            self.loss = TorchLoss()
        else:
            self.loss = TorchLoss.from_pytorch(loss)
        if optimizer is None:
            from zoo.orca.learn.optimizers.schedule import Default
            optimizer = SGD(learningrate_schedule=Default())
        if isinstance(optimizer, TorchOptimizer):
            optimizer = TorchOptim.from_pytorch(optimizer)
        elif isinstance(optimizer, OrcaOptimizer):
            optimizer = optimizer.get_optimizer()
        else:
            raise ValueError("Only PyTorch optimizer and orca optimizer are supported")
        self.log_dir = None
        self.app_name = None
        self.model_dir = model_dir
        self.model = TorchModel.from_pytorch(model)
        self.estimator = SparkEstimator(self.model, optimizer, model_dir, bigdl_type=bigdl_type)

    def _handle_dataframe(self, data, validation_data, feature_cols, label_cols):
        schema = data.schema
        train_rdd = data.rdd.map(lambda row: row_to_sample(row, schema, feature_cols, label_cols))
        train_feature_set = FeatureSet.sample_rdd(train_rdd)
        if validation_data is None:
            val_feature_set = None
        else:
            assert isinstance(validation_data, DataFrame), "validation_data should also be a " \
                                                           "DataFrame"
            val_feature_set = FeatureSet.sample_rdd(validation_data.rdd.map(
                lambda row: row_to_sample(row, schema, feature_cols, label_cols)))

        return train_feature_set, val_feature_set

    def _handle_xshards(self, data, validation_data):
        train_rdd = data.rdd.flatMap(xshard_to_sample)
        train_feature_set = FeatureSet.sample_rdd(train_rdd)
        if validation_data is None:
            val_feature_set = None
        else:
            assert isinstance(validation_data, SparkXShards), "validation_data should be a " \
                                                              "SparkXShards"
            val_feature_set = FeatureSet.sample_rdd(validation_data.rdd.flatMap(xshard_to_sample))
        return train_feature_set, val_feature_set

    def _hanle_data_loader(self, data, validation_data):
        train_feature_set = FeatureSet.pytorch_dataloader(data, "", "")
        if validation_data is None:
            val_feature_set = None
        else:
            assert isinstance(validation_data, DataLoader) or callable(data), \
                "validation_data should be a pytorch DataLoader or a callable data_creator"
            val_feature_set = FeatureSet.pytorch_dataloader(validation_data)

        return train_feature_set, val_feature_set

    def fit(self, data, epochs=1, batch_size=32, feature_cols=None, label_cols=None,
            validation_data=None, validation_metrics=None, checkpoint_trigger=None):
        from zoo.orca.learn.metrics import Metrics
        from zoo.orca.learn.trigger import Trigger

        end_trigger = MaxEpoch(epochs)
        assert batch_size > 0, "batch_size should be greater than 0"
        validation_metrics = Metrics.convert_metrics_list(validation_metrics)
        checkpoint_trigger = Trigger.convert_trigger(checkpoint_trigger)

        if self.log_dir is not None and self.app_name is not None:
            self.estimator.set_tensorboard(self.log_dir, self.app_name)

        if isinstance(data, SparkXShards):
            train_fset, val_fset = self._handle_xshards(data, validation_data)
            self.estimator.train(train_fset, self.loss, end_trigger, checkpoint_trigger,
                                 val_fset, validation_metrics, batch_size)
        elif isinstance(data, DataFrame):
            train_fset, val_fset = self._handle_dataframe(data, validation_data,
                                                          feature_cols, label_cols)
            self.estimator.train(train_fset, self.loss, end_trigger, checkpoint_trigger,
                                 val_fset, validation_metrics, batch_size)
        elif isinstance(data, DataLoader) or callable(data):
            train_fset, val_fset = self._hanle_data_loader(data, validation_data)
            self.estimator.train_minibatch(train_fset, self.loss, end_trigger,
                                           checkpoint_trigger, val_fset, validation_metrics)
        else:
            raise ValueError("Data and validation data should be SparkXShards, DataLoaders or "
                             "callable data_creators but get " + data.__class__.__name__)

        return self

    def predict(self, data, batch_size=4, feature_cols=None):
        from zoo.orca.learn.utils import convert_predict_rdd_to_xshard
        if isinstance(data, SparkXShards):
            from zoo.orca.data.utils import xshard_to_sample
            data_rdd = data.rdd.flatMap(xshard_to_sample)

        elif isinstance(data, DataFrame):
            schema = data.schema
            data_rdd = data.rdd.map(lambda row: row_to_sample(row, schema,
                                                              feature_cols, None))
        else:
            raise ValueError("Data should be XShards, each element needs to be {'x': a feature "
                             "numpy array}.")
        predicted_rdd = self.model.predict(data_rdd, batch_size=batch_size)

        if isinstance(data, SparkXShards):
            result = convert_predict_rdd_to_xshard(data, predicted_rdd)
        else:
            result = convert_predict_rdd_to_dataframe(data, predicted_rdd)
        return result

    def evaluate(self, data, batch_size=32, feature_cols=None, label_cols=None,
                 validation_metrics=None):
        from zoo.orca.data.utils import xshard_to_sample
        from zoo.orca.learn.metrics import Metrics

        assert data is not None, "validation data shouldn't be None"
        validation_metrics = Metrics.convert_metrics_list(validation_metrics)

        if isinstance(data, SparkXShards):
            val_feature_set = FeatureSet.sample_rdd(data.rdd.flatMap(xshard_to_sample))
            return self.estimator.evaluate(val_feature_set, validation_metrics, batch_size)
        elif isinstance(data, DataFrame):
            schema = data.schema
            val_feature_set = FeatureSet.sample_rdd(data.rdd.map(
                lambda row: row_to_sample(row, schema, feature_cols, label_cols)))
            return self.estimator.evaluate(val_feature_set, validation_metrics, batch_size)
        elif isinstance(data, DataLoader) or callable(data):
            val_feature_set = FeatureSet.pytorch_dataloader(data)
            return self.estimator.evaluate_minibatch(val_feature_set, validation_metrics)
        else:
            raise ValueError("Data should be a SparkXShards, a DataLoader or a callable "
                             "data_creator, but get " + data.__class__.__name__)

    def get_model(self):
        return self.model.to_pytorch()

    def save(self, model_path):
        raise NotImplementedError

    def load(self, checkpoint, loss=None):
        from zoo.orca.learn.utils import find_latest_checkpoint
        if loss is not None:
            from zoo.pipeline.api.torch import TorchLoss
            self.loss = TorchLoss.from_pytorch(loss)
        path, prefix, version = find_latest_checkpoint(checkpoint, model_type="pytorch")
        if path is None:
            raise ValueError("Cannot find PyTorch checkpoint, please check your checkpoint path.")
        self.load_orca_checkpoint(path, version=version, prefix=prefix)

    def load_orca_checkpoint(self, path, version, prefix=None):
        import os
        from bigdl.nn.layer import Model
        from bigdl.optim.optimizer import OptimMethod
        assert prefix is not None, "You should provide optimMethod prefix, " \
                                   "for example 'optimMethod-TorchModelf53bddcc'"
        try:
            self.model = Model.load(os.path.join(path, "model.{}".format(version)))
            optimizer = OptimMethod.load(os.path.join(path, "{}.{}".format(prefix, version)))
        except Exception:
            raise ValueError("Cannot load PyTorch checkpoint, please check your checkpoint path "
                             "and checkpoint type.")
        self.estimator = SparkEstimator(self.model, optimizer, self.model_dir)

    def load_latest_orca_checkpoint(self, path):
        self.load(checkpoint=path)

    def get_train_summary(self, tag=None):
        return self.estimator.get_train_summary(tag=tag)

    def get_validation_summary(self, tag=None):
        return self.estimator.get_validation_summary(tag=tag)

    def clear_gradient_clipping(self):
        """
        Clear gradient clipping parameters. In this case, gradient clipping will not be applied.
        In order to take effect, it needs to be called before fit.
        :return:
        """
        self.estimator.clear_gradient_clipping()

    def set_constant_gradient_clipping(self, min, max):
        """
        Set constant gradient clipping during the training process.
        In order to take effect, it needs to be called before fit.
        :param min: The minimum value to clip by.
        :param max: The maximum value to clip by.
        :return:
        """
        self.estimator.set_constant_gradient_clipping(min=min, max=max)

    def set_l2_norm_gradient_clipping(self, clip_norm):
        """
        Clip gradient to a maximum L2-Norm during the training process.
        In order to take effect, it needs to be called before fit.
        :param clip_norm: Gradient L2-Norm threshold.
        :return:
        """
        self.estimator.set_l2_norm_gradient_clipping(clip_norm=clip_norm)
