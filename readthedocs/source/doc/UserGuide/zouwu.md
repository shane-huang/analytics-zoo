# Zouwu User Guide

---
### **1. Training with AutoML**

To train a time series model with AutoML, use the AutoTS package.

The general workflow has two steps:

* create a [AutoTSTrainer]() to train a [TSPipeline](), save it to file to use later or elsewhere if you wish.
* use [TSPipeline]() to do prediction, evaluation, and incremental fitting as well.

Refer to [AutoTS notebook demo]() for demonstration how to use AutoTS to build a time series forcasting pipeline, and [AutoTS API Spec]() for more details.

#### **1.1 Install Dependencies**

Zouwu depends on below python libraries. 

```bash
python 3.6 or 3.7
pySpark
analytics-zoo
tensorflow>=1.15.0,<2.0.0
h5py==2.10.0
ray[tune]==0.8.4
psutil
aiohttp
setproctitle
pandas
scikit-learn>=0.20.0,<=0.22.0
requests
```

You can always install the dependencies manually, but it is highly recommended that you use Anaconda to prepare the environments, especially if you want to run automated training on a yarn cluster (yarn-client mode only). Analytics-zoo comes with a pre-defined dependency list, you can easily use below command to install all the dependencies for zouwu. 

```bash
conda create -n zoo python=3.7 #zoo is conda enviroment name, you can set another name you like.
conda activate zoo
pip install analytics-zoo[automl]==0.9.0.dev0 # or above
```

#### **1.2 Initialize Orca Context**

Training with AutoML (i.e. ```AutoTSTrainer.fit```) relies on [RayOnSpark]() to run, so you need to initalize [OrcaContext](https://testshanedoc.readthedocs.io/en/latest/doc/Orca/Overview/orca-context.html) with argument ```init_ray_on_spark=True``` before the training, and stop it after training is completed. 

[OrcaContext](https://testshanedoc.readthedocs.io/en/latest/doc/Orca/Overview/orca-context.html) is not needed if you just use the trained [TSPipeline]() for inference, evaluation or incremental training.


* local mode

```python
from zoo.orca import init_orca_context, stop_orca_context
init_orca_context(cluster_mode="local", cores=4, memory='2g', num_nodes=1, init_ray_on_spark=True)
```

* yarn client mode

```python
from zoo.orca import init_orca_context, stop_orca_context
init_orca_context(cluster_mode="yarn-client", 
                  num_nodes=2, cores=2, 
                  driver_memory="6g", driver_cores=4, 
                  conda_name='zoo', 
                  extra_memory_for_ray="10g", 
                  object_store_memory='5g')
```

#### **1.3 Create an AutoTSTrainer**

Create an AutoTSTrainer.

```python
from zoo.zouwu.autots.forecast import AutoTSTrainer

trainer = AutoTSTrainer(dt_col="datetime",
                        target_col="value",
                        horizon=1,
                        extra_features_col=None)
```
Some of the key arguments for AutoTSTrainer are:  
* dt_col: the column specifying datetime
* target_col: target column to predict
* horizon : num of steps to look forward
* extra_feature_col: a list of columns which are also included in input as features except target column
* search_alg: Optional(str). The search algorithm to use. We only support "bayesopt" and "skopt" for now. The default search_alg is None and variants will be generated according to the search method in search space.
* search_alg_params: Optional(Dict). params of search_alg.
* scheduler: Optional(str). Scheduler name. Allowed scheduler names are "fifo", "async_hyperband", "asynchyperband", "median_stopping_rule", "medianstopping", "hyperband", "hb_bohb", "pbt". The default scheduler is "fifo".
* scheduler_params: Optional(Dict). Necessary params of scheduler.

Refer to [AutoTSTrainer API]() for more details.

#### **1.4 Train a pipeline**

Use ```AutoTSTrainer.fit``` on train on input data and/or validation data with AutoML. A [TSPipeline]() will be returned. A TSPipeline include not only the mode, but also data preprocessing/post processing. 

```python
ts_pipeline = trainer.fit(train_df, validation_df)
```
Both [AutoTSTrainer]() and [TSPipeline]() accepts pandas data frames as input. An example input data looks like below. 

|datetime|value|extra_feature_1|extra_feature_2|
| --------|----- |---| ---|
|2019-06-06|1.2|1|2|
|2019-06-07|2.3|0|2|

You can use built-in [visualizaiton tool]() to inspect the training results. 

#### **1.5 Terminate Orca Context**

Stop [OrcaContext]() if you don't need to run ```AutoTSTrainer.fit``` anymore. 

```python
from zoo.orca import stop_orca_context
stop_orca_context()
```

#### **1.6 Using a trained pipeline**

Use ```TSPipeline.fit|evaluate|predict``` to train pipeline (incremental fitting), evaluate or predict.
Incremental fitting on TSPipeline just update the model weights the standard way, which does not involve AutoML. 
```python
#incremental fitting
ts_pipeline.fit(new_train_df, new_val_df, epochs=10)
#evaluate
ts_pipeline.evalute(val_df)
ts_pipeline.predict(test_df) 
```
Use ```TSPipeline.save|load``` to load from file or save to file.
```python
from zoo.zouwu.autots.forecast import TSPipeline
loaded_ppl = TSPipeline.load(file)
# ... do sth. e.g. incremental fitting
loaded_ppl.save(another_file)
```

---
### **2. Training without AutoML**

Zouwu provides below time series models for you to use without AutoML.  

* [LSTMForecaster]()
* [MTNetForecaster]()
* [TCMFForecaster]()
* [TCNForecaster]()

#### **2.1 Install Dependencies **

Zouwu depends on below python libraries. 

```bash
python 3.6 or 3.7
pySpark
analytics-zoo
tensorflow>=1.15.0,<2.0.0
h5py==2.10.0
ray[tune]==0.8.4
psutil
aiohttp
setproctitle
pandas
scikit-learn>=0.20.0,<=0.22.0
requests
```

You can always install the dependencies manually, but it is highly recommended that you use Anaconda to prepare the environments, especially if you want to run automated training on a yarn cluster (yarn-client mode only). Analytics-zoo comes with a pre-defined dependency list, you can easily use below command to install all the dependencies for zouwu. 

```bash
conda create -n zoo python=3.7 #zoo is conda enviroment name, you can set another name you like.
conda activate zoo
pip install analytics-zoo[automl]==0.9.0.dev0 # or above
```

#### **2.2 Initialize Orca Context **

Our built-in models support distributed training, which relies on [Orca](), so you need to initalize [OrcaContext](https://testshanedoc.readthedocs.io/en/latest/doc/Orca/Overview/orca-context.html) before training and stop it after training is completed. 

Note that [TCMFForecaster]() needs [RayOnSpark] for distributed training, you need to initilize [OrcaContext](https://testshanedoc.readthedocs.io/en/latest/doc/Orca/Overview/orca-context.html) with argument ```init_ray_on_spark=True```. 


* local mode

```python
from zoo.orca import init_orca_context, stop_orca_context
init_orca_context(cluster_mode="local", cores=4, memory='2g', num_nodes=1, init_ray_on_spark=True)
```

* yarn client mode

```python
from zoo.orca import init_orca_context, stop_orca_context
init_orca_context(cluster_mode="yarn-client", 
                  num_nodes=2, cores=2, 
                  driver_memory="6g", driver_cores=4, 
                  conda_name='zoo', 
                  extra_memory_for_ray="10g", 
                  object_store_memory='5g')
```
#### **2.3 LSTMForecaster**

LSTMForecaster is derived from [tfpark.KerasModels]().

Refer to [network traffic notebook]() for a real-world example and [LSTMForecaster API]() for more details. 

##### **2.3.1 Initialize**
```python
from zoo.zouwu.model.forecast.lstm_forecaster import LSTMForecaster
lstm_forecaster = LSTMForecaster(target_dim=1, 
                      feature_dim=4)
```
##### **2.3.2 Fit|Evalute|Predict**

The fit|evaluate|predict APIs are derived from tfpark.KerasModel, refer to [tfpark.KerasModel API]() for details.

```python
lstm_forecaster.fit(X,Y)
lstm_forecaster.predict(X)
lstm_forecaster.evaluate(X,Y)
```

Currently LSTMForecaster only supports univariant forecasting (i.e. to predict one series at a time). The input data shape for ```fit|evaluation|predict``` should match the arguments you used to create the forecaster. Specifically:

* X shape should be (num of samples, lookback, feature_dim)
* Y shape should be (num of samples, target_dim)
Where, feature_dim is the number of features as specified in Forecaster constructors. lookback is the number of time steps you want to look back in history. target_dim is the number of series to forecast at the same time as specified in Forecaster constructors and should be 1 here. If you want to do multi-step forecasting and use the second dimension as no. of steps to look forward, you won't get error but the performance may be uncertain and we don't recommend using that way.

#### **2.4 MTNetForecaster**

MTNetForecaster is derived from [tfpark.KerasModels]().

Refer to [network traffic notebook]() for a real-world example and [MTNetForecaster API]() for more details. 

##### **2.4.1 Initialize**
```python
from zoo.zouwu.model.forecast.mtnet_forecaster import MTNetForecaster
mtnet_forecaster = MTNetForecaster(target_dim=1,
                        feature_dim=4,
                        long_series_num=1,
                        series_length=3,
                        ar_window_size=2,
                        cnn_height=2)
```
##### **2.4.2 Fit|Evalute|Predict**

The fit|evaluate|predict APIs are derived from tfpark.KerasModel, refer to [tfpark.KerasModel API]() for details.

```python
mtnet_forecaster.fit(X,Y)
mtnet_forecaster.predict(X)
mtnet_forecaster.evaluate(X,Y)
```

* For univariant forecasting (i.e. to predict one series at a time), the input data shape for fit/evaluation/predict should match the arguments you used to create the forecaster. Specifically:

  - X shape should be (num of samples, lookback, feature_dim)
  - Y shape should be (num of samples, target_dim)
Where, feature_dim is the number of features as specified in Forecaster constructors. lookback is the number of time steps you want to look back in history. target_dim is the number of series to forecast at the same time as specified in Forecaster constructors and should be 1 here. If you want to do multi-step forecasting and use the second dimension as no. of steps to look forward, you won't get error but the performance may be uncertain and we don't recommend using that way.

* For multivariant forecasting (i.e. to predict several series at the same time), the input data shape should meet below criteria.

  - X shape should be (num of samples, lookback, feature_dim)
  - Y shape should be (num of samples, target_dim)
Where lookback should equal (lb_long_steps+1) * lb_long_stepsize, where lb_long_steps and lb_long_stepsize are as specified in MTNetForecaster constructor. target_dim should equal number of series in input.

#### **2.5 TCMFForecaster**

##### **2.5.1 Initialze**
```python
from zoo.zouwu.model.forecast.tcmf_forecaster import TCMFForecaster
model = TCMFForecaster(
        vbsize=128,
        hbsize=256,
        num_channels_X=[32, 32, 32, 32, 32, 1],
        num_channels_Y=[16, 16, 16, 16, 16, 1],
        kernel_size=7,
        dropout=0.1,
        rank=64,
        kernel_size_Y=7,
        learning_rate=0.0005,
        normalize=False,
        use_time=True,
        svd=True,)     
```
##### **2.5.2 Fit|Evalute|Predict**

* fit
```python
model.fit(
        x,
        val_len=24,
        start_date="2020-4-1",
        freq="1H",
        covariates=None,
        dti=None,
        period=24,
        y_iters=10,
        init_FX_epoch=100,
        max_FX_epoch=300,
        max_TCN_epoch=300,
        alt_iters=10,
        num_workers=num_workers_for_fit)
```
 * evaluate
 You can either call evalute directly 
 
```python
model.evaluate(target_value,
               metric=['mae'],
               target_covariates=None,
               target_dti=None,
               num_workers=num_workers_for_predict,
               )

```
Or predict first and then evaluate with metric name.
```python
yhat = model.predict(horizon,
                     future_covariates=None,
                     future_dti=None,
                     num_workers=num_workers_for_predict)

from zoo.automl.common.metrics import Evaluator
evaluate_mse = Evaluator.evaluate("mse", target_data, yhat)
```
 * incremental fit
```python
model.fit_incremental(x_incr, covariates_incr=None, dti_incr=None)
```

 * save and load
```python
model.save(dirname)
loaded_model = TCMFForecaster.load(dirname)
```
