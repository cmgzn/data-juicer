.. role:: raw-html-m2r(raw)
   :format: html


`[中文主页] <README_ZH.md>`_ | `[DJ-Cookbook] <#dj-cookbook>`_ | `[OperatorZoo] <docs/Operators.md>`_ | `[API] <https://modelscope.github.io/data-juicer>`_ | `[Awesome LLM Data] <docs/awesome_llm_data.md>`_

Data Processing for and with Foundation Models
==============================================

 :raw-html-m2r:`<img src="https://img.alicdn.com/imgextra/i1/O1CN01fUfM5A1vPclzPQ6VI_!!6000000006165-0-tps-1792-1024.jpg" width = "533" height = "300" alt="Data-Juicer"/>`


.. image:: https://img.shields.io/badge/language-Python-214870.svg
   :target: https://img.shields.io/badge/language-Python-214870.svg
   :alt: 


.. image:: https://img.shields.io/badge/license-Apache--2.0-000000.svg
   :target: https://img.shields.io/badge/license-Apache--2.0-000000.svg
   :alt: 


.. image:: https://img.shields.io/pypi/v/py-data-juicer?logo=pypi&color=026cad
   :target: https://pypi.org/project/py-data-juicer
   :alt: pypi version


.. image:: https://img.shields.io/docker/v/datajuicer/data-juicer?logo=docker&label=Docker&color=498bdf
   :target: https://hub.docker.com/r/datajuicer/data-juicer
   :alt: Docker version


.. image:: https://img.shields.io/badge/OSS%20latest-none?logo=docker&label=Docker&color=498bdf
   :target: https://dail-wlcb.oss-cn-wulanchabu.aliyuncs.com/data_juicer/docker_images/data-juicer-latest.tar.gz
   :alt: Docker on OSS


.. image:: https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FHYLcool%2Ff856b14416f08f73d05d32fd992a9c29%2Fraw%2Ftotal_cov.json
   :target: https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FHYLcool%2Ff856b14416f08f73d05d32fd992a9c29%2Fraw%2Ftotal_cov.json
   :alt: 



.. image:: https://img.shields.io/badge/DataModality-Text,Image,Audio,Video-brightgreen.svg
   :target: #dj-cookbook
   :alt: DataModality


.. image:: https://img.shields.io/badge/Usage-Cleaning,Synthesis,Analysis-FFD21E.svg
   :target: #dj-cookbook
   :alt: Usage


.. image:: https://img.shields.io/badge/ModelScope-Demos-4e29ff.svg?logo=data:image/svg+xml;base64,PHN2ZyB2aWV3Qm94PSIwIDAgMjI0IDEyMS4zMyIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KCTxwYXRoIGQ9Im0wIDQ3Ljg0aDI1LjY1djI1LjY1aC0yNS42NXoiIGZpbGw9IiM2MjRhZmYiIC8+Cgk8cGF0aCBkPSJtOTkuMTQgNzMuNDloMjUuNjV2MjUuNjVoLTI1LjY1eiIgZmlsbD0iIzYyNGFmZiIgLz4KCTxwYXRoIGQ9Im0xNzYuMDkgOTkuMTRoLTI1LjY1djIyLjE5aDQ3Ljg0di00Ny44NGgtMjIuMTl6IiBmaWxsPSIjNjI0YWZmIiAvPgoJPHBhdGggZD0ibTEyNC43OSA0Ny44NGgyNS42NXYyNS42NWgtMjUuNjV6IiBmaWxsPSIjMzZjZmQxIiAvPgoJPHBhdGggZD0ibTAgMjIuMTloMjUuNjV2MjUuNjVoLTI1LjY1eiIgZmlsbD0iIzM2Y2ZkMSIgLz4KCTxwYXRoIGQ9Im0xOTguMjggNDcuODRoMjUuNjV2MjUuNjVoLTI1LjY1eiIgZmlsbD0iIzYyNGFmZiIgLz4KCTxwYXRoIGQ9Im0xOTguMjggMjIuMTloMjUuNjV2MjUuNjVoLTI1LjY1eiIgZmlsbD0iIzM2Y2ZkMSIgLz4KCTxwYXRoIGQ9Im0xNTAuNDQgMHYyMi4xOWgyNS42NXYyNS42NWgyMi4xOXYtNDcuODR6IiBmaWxsPSIjNjI0YWZmIiAvPgoJPHBhdGggZD0ibTczLjQ5IDQ3Ljg0aDI1LjY1djI1LjY1aC0yNS42NXoiIGZpbGw9IiMzNmNmZDEiIC8+Cgk8cGF0aCBkPSJtNDcuODQgMjIuMTloMjUuNjV2LTIyLjE5aC00Ny44NHY0Ny44NGgyMi4xOXoiIGZpbGw9IiM2MjRhZmYiIC8+Cgk8cGF0aCBkPSJtNDcuODQgNzMuNDloLTIyLjE5djQ3Ljg0aDQ3Ljg0di0yMi4xOWgtMjUuNjV6IiBmaWxsPSIjNjI0YWZmIiAvPgo8L3N2Zz4K
   :target: https://modelscope.cn/studios?name=Data-Jiucer&page=1&sort=latest&type=1
   :alt: ModelScope- Demos


.. image:: https://img.shields.io/badge/🤗HuggingFace-Demos-4e29ff.svg
   :target: https://huggingface.co/spaces?&search=datajuicer
   :alt: HuggingFace- Demos



.. image:: https://img.shields.io/badge/Doc-DJ_Cookbook-blue?logo=Markdown
   :target: #dj-cookbook
   :alt: Document_List


.. image:: https://img.shields.io/badge/文档-DJ指南-blue?logo=Markdown
   :target: README_ZH.md#dj-cookbook
   :alt: 文档列表


.. image:: https://img.shields.io/badge/Doc-OperatorZoo-blue?logo=Markdown
   :target: docs/Operators.md
   :alt: OpZoo


.. image:: http://img.shields.io/badge/cs.LG-1.0Paper(SIGMOD'24
   :target: https://arxiv.org/abs/2309.02033
   :alt: Paper


.. image:: http://img.shields.io/badge/cs.AI-2.0Paper-B31B1B?logo=arxiv&logoColor=red
   :target: https://arxiv.org/abs/2501.14755
   :alt: Paper


Data-Juicer is a one-stop system to process text and multimodal data for and with foundation models (typically LLMs).
We provide a `playground <http://8.138.149.181/>`_ with a managed JupyterLab. `Try Data-Juicer <http://8.138.149.181/>`_ straight away in your browser! If you find Data-Juicer useful for your research or development, please kindly support us by starting it (then be instantly notified of our new releases) and citing our `works <#references>`_.

`Platform for AI of Alibaba Cloud (PAI) <https://www.aliyun.com/product/bigdata/learn>`_ has cited our work and integrated Data-Juicer into its data processing products. PAI is an AI Native large model and AIGC engineering platform that provides dataset management, computing power management, model tool chain, model development, model training, model deployment, and AI asset management. For documentation on data processing, please refer to: `PAI-Data Processing for Large Models <https://help.aliyun.com/zh/pai/user-guide/components-related-to-data-processing-for-foundation-models/?spm=a2c4g.11186623.0.0.3e9821a69kWdvX>`_.

Data-Juicer is being actively updated and maintained. We will periodically enhance and add more features, data recipes and datasets.  We welcome you to join us (via issues, PRs, `Slack <https://join.slack.com/t/data-juicer/shared_invite/zt-23zxltg9d-Z4d3EJuhZbCLGwtnLWWUDg?spm=a2c22.12281976.0.0.7a8253f30mgpjw>`_  channel, `DingDing <https://qr.dingtalk.com/action/joingroup?code=v1,k1,YFIXM2leDEk7gJP5aMC95AfYT+Oo/EP/ihnaIEhMyJM=&_dt_no_comment=1&origin=11>`_ group, ...), in promoting data-model co-development along with research and applications of foundation models!



Table of Contents
=================


* `News <#news>`_
* `Why Data-Juicer? <#why-data-juicer>`_
* `DJ-Cookbook <#dj-cookbook>`_

  * `Curated Resources <#curated-resources>`_
  * `Coding with Data-Juicer (DJ) <#coding-with-data-juicer-dj>`_
  * `Use Cases \& Data Recipes <#use-cases--data-recipes>`_
  * `Interactive Examples <#interactive-examples>`_

* `Installation <#installation>`_

  * `Prerequisites <#prerequisites>`_
  * `From Source for Specific Scenarios <#from-source-for-specific-scenarios>`_
  * `From Source for Specific OPs <#from-source-for-specific-ops>`_
  * `Using pip <#using-pip>`_
  * `Using Docker <#using-docker>`_
  * `Installation check <#installation-check>`_
  * `For Video-related Operators <#for-video-related-operators>`_

* `Quick Start <#quick-start>`_

  * `Dataset Configuration <#dataset-configuration>`_
  * `Data Processing <#data-processing>`_
  * `Distributed Data Processing <#distributed-data-processing>`_
  * `Data Analysis <#data-analysis>`_
  * `Data Visualization <#data-visualization>`_
  * `Build Up Config Files <#build-up-config-files>`_
  * `Sandbox <#sandbox>`_
  * `Preprocess Raw Data (Optional) <#preprocess-raw-data-optional>`_
  * `For Docker Users <#for-docker-users>`_

* `License <#license>`_
* `Contributing <#contributing>`_
* `Acknowledgement <#acknowledgement>`_
* `References <#references>`_

Why Data-Juicer?
----------------

:raw-html-m2r:`<img src="https://img.alicdn.com/imgextra/i2/O1CN01EteoQ31taUweAW1UE_!!6000000005918-2-tps-4034-4146.png" align="center" width="600" />`


* 
  **Systematic & Reusable**\ :
  Empowering users with a systematic library of 100+ core `OPs <docs/Operators.md>`_\ , and 50+ reusable config recipes and 
  dedicated toolkits, designed to
  function independently of specific multimodal LLM datasets and processing pipelines. Supporting data analysis, cleaning, and synthesis in pre-training, post-tuning, en, zh, and more scenarios.

* 
  **User-Friendly & Extensible**\ : 
  Designed for simplicity and flexibility, with easy-start `guides <#quick-start>`_\ , and `DJ-Cookbook <#dj-cookbook>`_ containing fruitful demo usages. Feel free to `implement your own OPs <docs/DeveloperGuide.md#build-your-own-ops>`_ for customizable data processing.

* 
  **Efficient & Robust**\ : Providing performance-optimized `parallel data processing <docs/Distributed.md>`_ (Aliyun-PAI\Ray\CUDA\OP Fusion),
  faster with less resource usage, verified in large-scale production environments.


* **Effect-Proven & Sandbox**\ : Supporting data-model co-development, enabling rapid iteration
  through the `sandbox laboratory <docs/Sandbox.md>`_\ , and providing features such as feedback loops and visualization, so that you can better understand and improve your data and models. Many effect-proven datasets and models have been derived from DJ, in scenarios such as pre-training, text-to-video and image-to-text generation.

  .. image:: https://img.alicdn.com/imgextra/i2/O1CN017U7Zz31Y7XtCJ5GOz_!!6000000003012-0-tps-3640-1567.jpg
     :target: https://img.alicdn.com/imgextra/i2/O1CN017U7Zz31Y7XtCJ5GOz_!!6000000003012-0-tps-3640-1567.jpg
     :alt: Data-in-the-loop
   

DJ-Cookbook
-----------

Curated Resources
^^^^^^^^^^^^^^^^^


* `KDD-Tutorial <https://modelscope.github.io/data-juicer/_static/tutorial_kdd24.html>`_
* `Awesome LLM-Data <docs/awesome_llm_data.md>`_
* `"Bad" Data Exhibition <docs/BadDataExhibition.md>`_

Coding with Data-Juicer (DJ)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^


* Basics

  * `Overview of DJ <README.md>`_
  * `Quick Start <#quick-start>`_
  * `Configuration <docs/RecipeGallery.md>`_
  * `Data Format Conversion <tools/fmt_conversion/README.md>`_

* Lookup Materials

  * `DJ OperatorZoo <docs/Operators.md>`_
  * `API references <https://modelscope.github.io/data-juicer/>`_

* Advanced

  * `Developer Guide <docs/DeveloperGuide.md>`_
  * `Preprocess Tools <tools/preprocess/README.md>`_
  * `Postprocess Tools <tools/postprocess/README.md>`_
  * `Sandbox <docs/Sandbox.md>`_
  * `API Service <docs/DJ_service.md>`_
  * `Data Scoring <tools/quality_classifier/README.md>`_
  * `Auto Evaluation <tools/evaluator/README.md>`_
  * `Third-parties Integration <thirdparty/LLM_ecosystems/README.md>`_

Use Cases & Data Recipes
^^^^^^^^^^^^^^^^^^^^^^^^


* `Data Recipe Gallery <docs/RecipeGallery.md>`_

  * Data-Juicer Minimal Example Recipe
  * Reproducing Open Source Text Datasets
  * Improving Open Source Pre-training Text Datasets
  * Improving Open Source Post-tuning Text Datasets
  * Synthetic Contrastive Learning Image-text Datasets
  * Improving Open Source Image-text Datasets
  * Basic Example Recipes for Video Data
  * Synthesizing Human-centric Video Benchmarks
  * Improving Existing Open Source Video Datasets

* Data-Juicer related Competitions

  * `Better Synth <https://tianchi.aliyun.com/competition/entrance/532251>`_\ , explore the impact of large model synthetic data on image understanding ability with DJ-Sandbox Lab and multimodal large models
  * `Modelscope-Sora Challenge <https://tianchi.aliyun.com/competition/entrance/532219>`_\ , based on Data-Juicer and `EasyAnimate <https://github.com/aigc-apps/EasyAnimate>`_ framework,  optimize data and train SORA-like small models to generate better videos
  * `Better Mixture <https://tianchi.aliyun.com/competition/entrance/532174>`_\ , only adjust data mixing and sampling strategies for given multiple candidate datasets
  * FT-Data Ranker (\ `1B Track <https://tianchi.aliyun.com/competition/entrance/532157>`_\ , `7B Track <https://tianchi.aliyun.com/competition/entrance/532158>`_\ ), For a specified candidate dataset, only adjust the data filtering and enhancement strategies
  * `Kolors-LoRA Stylized Story Challenge <https://tianchi.aliyun.com/competition/entrance/532254>`_\ , based on Data-Juicer and `DiffSynth-Studio <https://github.com/modelscope/DiffSynth-Studio>`_ framework, explore Diffusion model fine-tuning

* `DJ-SORA <docs/DJ_SORA.md>`_
* Based on Data-Juicer and `AgentScope <https://github.com/modelscope/agentscope>`_ framework, leverage `agents to call DJ Filters <./demos/api_service/react_data_filter_process.ipynb>`_ and `call DJ Mappers <./demos/api_service/react_data_mapper_process.ipynb>`_

Interactive Examples
^^^^^^^^^^^^^^^^^^^^


* Introduction to Data-Juicer [\ `ModelScope <https://modelscope.cn/studios/Data-Juicer/overview_scan/summary>`_\ ] [\ `HuggingFace <https://huggingface.co/spaces/datajuicer/overview_scan>`_\ ]
* Data Visualization:

  * Basic Statistics [\ `ModelScope <https://modelscope.cn/studios/Data-Juicer/data_visulization_statistics/summary>`_\ ] [\ `HuggingFace <https://huggingface.co/spaces/datajuicer/data_visualization_statistics>`_\ ]
  * Lexical Diversity [\ `ModelScope <https://modelscope.cn/studios/Data-Juicer/data_visulization_diversity/summary>`_\ ] [\ `HuggingFace <https://huggingface.co/spaces/datajuicer/data_visualization_diversity>`_\ ]
  * Operator Insight (Single OP) [\ `ModelScope <https://modelscope.cn/studios/Data-Juicer/data_visualization_op_insight/summary>`_\ ] [\ `HuggingFace <https://huggingface.co/spaces/datajuicer/data_visualization_op_insight>`_\ ]
  * Operator Effect (Multiple OPs) [\ `ModelScope <https://modelscope.cn/studios/Data-Juicer/data_visulization_op_effect/summary>`_\ ] [\ `HuggingFace <https://huggingface.co/spaces/datajuicer/data_visualization_op_effect>`_\ ]

* Data Processing:

  * Scientific Literature (e.g. `arXiv <https://info.arxiv.org/help/bulk_data_s3.html>`_\ ) [\ `ModelScope <https://modelscope.cn/studios/Data-Juicer/process_sci_data/summary>`_\ ] [\ `HuggingFace <https://huggingface.co/spaces/datajuicer/process_sci_data>`_\ ]
  * Programming Code (e.g. `TheStack <https://huggingface.co/datasets/bigcode/the-stack>`_\ ) [\ `ModelScope <https://modelscope.cn/studios/Data-Juicer/process_code_data/summary>`_\ ] [\ `HuggingFace <https://huggingface.co/spaces/datajuicer/process_code_data>`_\ ]
  * Chinese Instruction Data (e.g. `Alpaca-CoT <https://huggingface.co/datasets/QingyiSi/Alpaca-CoT>`_\ ) [\ `ModelScope <https://modelscope.cn/studios/Data-Juicer/process_sft_zh_data/summary>`_\ ] [\ `HuggingFace <https://huggingface.co/spaces/datajuicer/process_cft_zh_data>`_\ ]

* Tool Pool:

  * Dataset Splitting by Language [\ `ModelScope <https://modelscope.cn/studios/Data-Juicer/tool_dataset_splitting_by_language/summary>`_\ ] [\ `HuggingFace <https://huggingface.co/spaces/datajuicer/tool_dataset_splitting_by_language>`_\ ]
  * Quality Classifier for CommonCrawl [\ `ModelScope <https://modelscope.cn/studios/Data-Juicer/tool_quality_classifier/summary>`_\ ] [\ `HuggingFace <https://huggingface.co/spaces/datajuicer/tool_quality_classifier>`_\ ]
  * Auto Evaluation on `HELM <https://github.com/stanford-crfm/helm>`_ [\ `ModelScope <https://modelscope.cn/studios/Data-Juicer/auto_evaluation_helm/summary>`_\ ] [\ `HuggingFace <https://huggingface.co/spaces/datajuicer/auto_evaluation_helm>`_\ ]
  * Data Sampling and Mixture [\ `ModelScope <https://modelscope.cn/studios/Data-Juicer/data_mixture/summary>`_\ ] [\ `HuggingFace <https://huggingface.co/spaces/datajuicer/data_mixture>`_\ ]

* Data Processing Loop [\ `ModelScope <https://modelscope.cn/studios/Data-Juicer/data_process_loop/summary>`_\ ] [\ `HuggingFace <https://huggingface.co/spaces/datajuicer/data_process_loop>`_\ ]

Installation
------------

Prerequisites
^^^^^^^^^^^^^


* Recommend Python>=3.9,<=3.10
* gcc >= 5 (at least C++14 support)

From Source for Specific Scenarios
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


* 
  Run the following commands to install the latest basic ``data_juicer`` version in
  editable mode:

  .. code-block:: shell

     cd <path_to_data_juicer>
     pip install -v -e .

* 
  Some OPs rely on some other too large or low-platform-compatibility third-party libraries. You can install optional dependencies as needed:

.. code-block:: shell

   cd <path_to_data_juicer>
   pip install -v -e .  # Install minimal dependencies, which support the basic functions
   pip install -v -e .[tools] # Install a subset of tools dependencies

The dependency options are listed below:

.. list-table::
   :header-rows: 1

   * - Tag
     - Description
   * - ``.`` or ``.[mini]``
     - Install minimal dependencies for basic Data-Juicer.
   * - ``.[all]``
     - Install dependencies for all OPs except sandbox.
   * - ``.[sci]``
     - Install dependencies for OPs related to scientific usage.
   * - ``.[dist]``
     - Install dependencies for additional distributed data processing.
   * - ``.[dev]``
     - Install dependencies for developing the package as contributors.
   * - ``.[tools]``
     - Install dependencies for dedicated tools, such as quality classifiers.
   * - ``.[sandbox]``
     - Install all dependencies for sandbox.


From Source for Specific OPs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^


* Install dependencies for specific OPs

With the growth of the number of OPs, the dependencies of all OPs become very heavy. Instead of using the command ``pip install -v -e .[all]`` to install all dependencies,
we provide two alternative, lighter options:


* 
  Automatic Minimal Dependency Installation: During the execution of Data-Juicer, minimal dependencies will be automatically installed. This allows for immediate execution, but may potentially lead to dependency conflicts.

* 
  Manual Minimal Dependency Installation: To manually install minimal dependencies tailored to a specific execution configuration, run the following command:

  .. code-block:: shell

     # only for installation from source
     python tools/dj_install.py --config path_to_your_data-juicer_config_file

     # use command line tool
     dj-install --config path_to_your_data-juicer_config_file

Using pip
^^^^^^^^^


* Run the following command to install the latest released ``data_juicer`` using ``pip``\ :

.. code-block:: shell

   pip install py-data-juicer


* **Note**\ :

  * only the basic APIs in ``data_juicer`` and two basic tools
    (data `processing <#data-processing>`_ and `analysis <#data-analysis>`_\ ) are available in this way. If you want customizable
    and complete functions, we recommend you install ``data_juicer`` `from source <#from-source>`_.
  * The release versions from pypi have a certain lag compared to the latest version from source.
    So if you want to follow the latest functions of ``data_juicer``\ , we recommend you install `from source <#from-source>`_.

Using Docker
^^^^^^^^^^^^


* 
  You can


  * 
    either pull our pre-built image from DockerHub:

    .. code-block:: shell

       docker pull datajuicer/data-juicer:<version_tag>


    * if you can not connect ot DockerHub, please use other registry mirrors (you can find some from the Internet):
      .. code-block:: shell

         docker pull <other_registry_mirror>/datajuicer/data-juicer:<version_tag>

  * 
    or run the following command to build the docker image including the
    latest ``data-juicer`` with provided `Dockerfile <Dockerfile>`_\ :

    .. code-block:: shell

       docker build -t datajuicer/data-juicer:<version_tag> .

  * 
    The format of ``<version_tag>`` is like ``v0.2.0``\ , which is the same as the release version tag.

Installation check
^^^^^^^^^^^^^^^^^^

.. code-block:: python

   import data_juicer as dj
   print(dj.__version__)

For Video-related Operators
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Before using video-related operators, **FFmpeg** should be installed and accessible via the $PATH environment variable.

You can install FFmpeg using package managers(e.g. sudo apt install ffmpeg on Debian/Ubuntu, brew install ffmpeg on OS X) or visit the `official ffmpeg link <https://ffmpeg.org/download.html>`_.

Check if your environment path is set correctly by running the ffmpeg command from the terminal.


.. raw:: html

   <p align="right"><a href="#table">🔼 back to index</a></p>


Quick Start
-----------

Dataset Configuration
^^^^^^^^^^^^^^^^^^^^^

DJ supports various dataset input types, including local files, remote datasets like huggingface; it also supports data validation and data mixture.

Two ways to configure a input file


* Simple scenarios, single path for local/HF file
  .. code-block:: yaml

     dataset_path: '/path/to/your/dataset'  # path to your dataset directory or file

* advanced method, supports sub-configuration items and more features
  .. code-block:: yaml

     dataset:
     configs:
       - type: 'local'
         path: 'path/to/your/dataset' # path to your dataset directory or file

Refer to `Dataset Configuration Guide <docs/DatasetCfg.md>`_ for more details.

Data Processing
^^^^^^^^^^^^^^^


* Run ``process_data.py`` tool or ``dj-process`` command line tool with your config as the argument to process
  your dataset.

.. code-block:: shell

   # only for installation from source
   python tools/process_data.py --config configs/demo/process.yaml

   # use command line tool
   dj-process --config configs/demo/process.yaml


* 
  **Note:** For some operators that involve third-party models or resources that are not stored locally on your computer, it might be slow for the first running because these ops need to download corresponding resources into a directory first.
  The default download cache directory is ``~/.cache/data_juicer``. Change the cache location by setting the shell environment variable, ``DATA_JUICER_CACHE_HOME`` to another directory, and you can also change ``DATA_JUICER_MODELS_CACHE`` or ``DATA_JUICER_ASSETS_CACHE`` in the same way:

* 
  **Note:** When using operators with third-party models, it's necessary to declare the corresponding ``mem_required`` in the configuration file (you can refer to the settings in the ``config_all.yaml`` file). During runtime, Data-Juicer will control the number of processes based on memory availability and the memory requirements of the operator models to achieve better data processing efficiency. When running with CUDA environments, if the mem_required for an operator is not declared correctly, it could potentially lead to a CUDA Out of Memory issue.

.. code-block:: shell

   # cache home
   export DATA_JUICER_CACHE_HOME="/path/to/another/directory"
   # cache models
   export DATA_JUICER_MODELS_CACHE="/path/to/another/directory/models"
   # cache assets
   export DATA_JUICER_ASSETS_CACHE="/path/to/another/directory/assets"


* **Flexible Programming Interface:**
  We provide various simple interfaces for users to choose from as follows. 
  ```python
  #... init op & dataset ...

Chain call style, support single operator or operator list
==========================================================

dataset = dataset.process(op)
dataset = dataset.process([op1, op2])

Functional programming style for quick integration or script prototype iteration
================================================================================

dataset = op(dataset)
dataset = op.run(dataset)

.. code-block::



   ### Distributed Data Processing

   We have now implemented multi-machine distributed data processing based on [RAY](https://www.ray.io/). The corresponding demos can be run using the following commands:

   ```shell
   # Run text data processing
   python tools/process_data.py --config ./demos/process_on_ray/configs/demo.yaml
   # Run video data processing
   python tools/process_data.py --config ./demos/process_video_on_ray/configs/demo.yaml


* To run data processing across multiple machines, it is necessary to ensure that all distributed nodes can access the corresponding data paths (for example, by mounting the respective data paths on a file-sharing system such as NAS).
* The deduplication operators for RAY mode are different from the single-machine version, and all those operators are prefixed with ``ray``\ , e.g. ``ray_video_deduplicator`` and ``ray_document_deduplicator``.
* More details can be found in the doc for `distributed processing <docs/Distributed.md>`_.

..

   Users can also opt not to use RAY and instead split the dataset to run on a cluster with `Slurm <https://slurm.schedmd.com/>`_. In this case, please use the default Data-Juicer without RAY.
   `Aliyun PAI-DLC <https://www.aliyun.com/activity/bigdata/pai-dlc>`_ supports the RAY framework, Slurm framework, etc. Users can directly create RAY jobs and Slurm jobs on the DLC cluster.


Data Analysis
^^^^^^^^^^^^^


* Run ``analyze_data.py`` tool or ``dj-analyze`` command line tool with your config as the argument to analyze your dataset.

.. code-block:: shell

   # only for installation from source
   python tools/analyze_data.py --config configs/demo/analyzer.yaml

   # use command line tool
   dj-analyze --config configs/demo/analyzer.yaml

   # you can also use auto mode to avoid writing a recipe. It will analyze a small
   # part (e.g. 1000 samples, specified by argument `auto_num`) of your dataset 
   # with all Filters that produce stats.
   dj-analyze --auto --dataset_path xx.jsonl [--auto_num 1000]


* **Note:** Analyzer only computes stats for Filters that produce stats or other OPs that produce tags/categories in meta. So other OPs will be ignored in the analysis process. We use the following registries to decorate OPs:

  * ``NON_STATS_FILTERS``\ : decorate Filters that **DO NOT** produce any stats.
  * ``TAGGING_OPS``\ : decorate OPs that **DO** produce tags/categories in meta field.

Data Visualization
^^^^^^^^^^^^^^^^^^


* Run ``app.py`` tool to visualize your dataset in your browser.
* **Note**\ : only available for installation from source.

.. code-block:: shell

   streamlit run app.py

Build Up Config Files
^^^^^^^^^^^^^^^^^^^^^


* Config files specify some global arguments, and an operator list for the
  data process. You need to set:

  * Global arguments: input/output dataset path, number of workers, etc.
  * Operator list: list operators with their arguments used to process the dataset.

* You can build up your own config files by:

  * ➖：Modify from our example config file `\ ``config_all.yaml`` <configs/config_all.yaml>`_ which includes **all** ops and default
    arguments. You just need to **remove** ops that you won't use and refine
    some arguments of ops.
  * ➕：Build up your own config files **from scratch**. You can refer our
    example config file `\ ``config_all.yaml`` <configs/config_all.yaml>`_\ , `op documents <docs/Operators.md>`_\ , and advanced `Build-Up Guide for developers <docs/DeveloperGuide.md#build-your-own-configs>`_.
  * Besides the yaml files, you also have the flexibility to specify just
    one (of several) parameters on the command line, which will override
    the values in yaml files.

.. code-block:: shell

   python xxx.py --config configs/demo/process.yaml --language_id_score_filter.lang=en


* 
  The basic config format and definition is shown below.


  .. image:: https://img.alicdn.com/imgextra/i1/O1CN01uXgjgj1khWKOigYww_!!6000000004715-0-tps-1745-871.jpg
     :target: https://img.alicdn.com/imgextra/i1/O1CN01uXgjgj1khWKOigYww_!!6000000004715-0-tps-1745-871.jpg
     :alt: Basic config example of format and definition


Sandbox
^^^^^^^

The data sandbox laboratory (DJ-Sandbox) provides users with the best practices for continuously producing data recipes. It features low overhead, portability, and guidance.


* In the sandbox, users can quickly experiment, iterate, and refine data recipes based on small-scale datasets and models, before scaling up to produce high-quality data to serve large-scale models.
* In addition to the basic data optimization and recipe refinement features offered by Data-Juicer, users can seamlessly use configurable components such as data probe and analysis, model training and evaluation, and data and model feedback-based recipe refinement to form a complete one-stop data-model research and development pipeline.

The sandbox is run using the following commands by default, and for more information and details, please refer to the `sandbox documentation <docs/Sandbox.md>`_.

.. code-block:: shell

   python tools/sandbox_starter.py --config configs/demo/sandbox/sandbox.yaml

Preprocess Raw Data (Optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


* Our Formatters support some common input dataset formats for now:

  * Multi-sample in one file: jsonl/json, parquet, csv/tsv, etc.
  * Single-sample in one file: txt, code, docx, pdf, etc.

* However, data from different sources are complicated and diverse. Such as:

  * `Raw arXiv data downloaded from S3 <https://info.arxiv.org/help/bulk_data_s3.html>`_ include thousands of tar files and even more gzip files in them, and expected tex files are embedded in the gzip files so they are hard to obtain directly.
  * Some crawled data include different kinds of files (pdf, html, docx, etc.). And extra information like tables, charts, and so on is hard to extract.

* It's impossible to handle all kinds of data in Data-Juicer, issues/PRs are welcome to contribute to processing new data types!
* Thus, we provide some **common preprocessing tools** in `\ ``tools/preprocess`` <tools/preprocess/>`_ for you to preprocess these data.

  * You are welcome to make your contributions to new preprocessing tools for the community.
  * We **highly recommend** that complicated data can be preprocessed to jsonl or parquet files.

For Docker Users
^^^^^^^^^^^^^^^^


* If you build or pull the docker image of ``data-juicer``\ , you can run the commands or tools mentioned above using this docker image.
* Run directly:

.. code-block:: shell

   # run the data processing directly
   docker run --rm  # remove container after the processing
     --privileged \
     --shm-size 256g \
     --network host \
     --gpus all \
     --name dj  # name of the container
     -v <host_data_path>:<image_data_path>  # mount data or config directory into the container
     -v ~/.cache/:/root/.cache/  # mount the cache directory into the container to reuse caches and models (recommended)
     datajuicer/data-juicer:<version_tag>  # image to run
     dj-process --config /path/to/config.yaml  # similar data processing commands


* Or enter into the running container and run commands in editable mode:

.. code-block:: shell

   # start the container
   docker run -dit  # run the container in the background
     --privileged \
     --shm-size 256g \
     --network host \
     --gpus all \
     --rm \
     --name dj \
     -v <host_data_path>:<image_data_path> \
     -v ~/.cache/:/root/.cache/ \
     datajuicer/data-juicer:latest /bin/bash

   # enter into this container and then you can use data-juicer in editable mode
   docker exec -it <container_id> bash


.. raw:: html

   <p align="right"><a href="#table">🔼 back to index</a></p>


License
-------

Data-Juicer is released under Apache License 2.0.

Contributing
------------

We are in a rapidly developing field and greatly welcome contributions of new
features, bug fixes, and better documentation. Please refer to
`How-to Guide for Developers <docs/DeveloperGuide.md>`_.

Acknowledgement
---------------

Data-Juicer is used across various foundation model applications and research initiatives, such as industrial scenarios in Alibaba Tongyi and Alibaba Cloud's platform for AI (PAI).
We look forward to more of your experience, suggestions, and discussions for collaboration!

Data-Juicer thanks many community `contributors <https://github.com/modelscope/data-juicer/graphs/contributors>`_ and open-source projects, such as
`Huggingface-Datasets <https://github.com/huggingface/datasets>`_\ , `Bloom <https://huggingface.co/bigscience/bloom>`_\ , `RedPajama <https://github.com/togethercomputer/RedPajama-Data/tree/rp_v1>`_\ , `Arrow <https://github.com/apache/arrow>`_\ , `Ray <https://github.com/ray-project/ray>`_\ , ....

References
----------

If you find Data-Juicer useful for your research or development, please kindly cite the following works, `1.0paper <https://arxiv.org/abs/2309.02033>`_\ , `2.0paper <https://arxiv.org/abs/2501.14755>`_.

.. code-block::

   @inproceedings{djv1,
     title={Data-Juicer: A One-Stop Data Processing System for Large Language Models},
     author={Daoyuan Chen and Yilun Huang and Zhijian Ma and Hesen Chen and Xuchen Pan and Ce Ge and Dawei Gao and Yuexiang Xie and Zhaoyang Liu and Jinyang Gao and Yaliang Li and Bolin Ding and Jingren Zhou},
     booktitle={International Conference on Management of Data},
     year={2024}
   }

   @article{djv2,
     title={Data-Juicer 2.0: Cloud-Scale Adaptive Data Processing for Foundation Models},
     author={Chen, Daoyuan and Huang, Yilun and Pan, Xuchen and Jiang, Nana and Wang, Haibin and Ge, Ce and Chen, Yushuo and Zhang, Wenhao and Ma, Zhijian and Zhang, Yilei and Huang, Jun and Lin, Wei and Li, Yaliang and Ding, Bolin and Zhou, Jingren},
     journal={arXiv preprint arXiv:2501.14755},
     year={2024}
   }


.. raw:: html

   <details>
   <summary> More data-related papers from the Data-Juicer Team:
   </summary>>

   - [Data-Juicer Sandbox: A Feedback-Driven Suite for Multimodal Data-Model Co-development](https://arxiv.org/abs/2407.11784)

   - [ImgDiff: Contrastive Data Synthesis for Vision Large Language Models](https://arxiv.org/abs/2408.04594)

   - [HumanVBench: Exploring Human-Centric Video Understanding Capabilities of MLLMs with Synthetic Benchmark Data](https://arxiv.org/abs/2412.17574)

   - [The Synergy between Data and Multi-Modal Large Language Models: A Survey from Co-Development Perspective](https://arxiv.org/abs/2407.08583)

   - [Diversity as a Reward: Fine-Tuning LLMs on a Mixture of Domain-Undetermined Data](https://www.arxiv.org/abs/2502.04380)

   - [MindGym: Enhancing Vision-Language Models via Synthetic Self-Challenging Questions](https://arxiv.org/abs/2503.09499)

   - [BiMix: A Bivariate Data Mixing Law for Language Model Pretraining](https://arxiv.org/abs/2405.14908)

   </details>



.. raw:: html

   <p align="right"><a href="#table">🔼 back to index</a></p>

.. toctree::
   :maxdepth: 2
   :glob:
   :caption: API Reference

   data_juicer.core
   data_juicer.ops
   data_juicer.ops.filter
   data_juicer.ops.mapper
   data_juicer.ops.deduplicator
   data_juicer.ops.selector
   data_juicer.ops.common
   data_juicer.analysis
   data_juicer.config
   data_juicer.format

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`