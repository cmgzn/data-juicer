.. _Data Processing for and with Foundation Models:
.. role:: raw-html-m2r(raw)
   :format: html


`[中文主页] <README_ZH>`_ | `[DJ-Cookbook] <#dj-cookbook>`_ | `[OperatorZoo] <docs/Operators>`_ | `[API] <https://modelscope.github.io/data-juicer>`_ | `[Awesome LLM Data] <docs/awesome_llm_data>`_

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
   :target: README_ZH#dj-cookbook
   :alt: 文档列表


.. image:: https://img.shields.io/badge/Doc-OperatorZoo-blue?logo=Markdown
   :target: docs/Operators
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

News
----


* 🎉 [2025-05-06] Our work of `Data-Juicer Sandbox <https://arxiv.org/abs/2407.11784>`_ has been accepted as a **Spotlight** by *ICML 2025* (top 2.6% of all submissions)!
* 
  .. image:: https://img.alicdn.com/imgextra/i4/O1CN01kUiDtl1HVxN6G56vN_!!6000000000764-2-tps-43-19.png
     :target: https://img.alicdn.com/imgextra/i4/O1CN01kUiDtl1HVxN6G56vN_!!6000000000764-2-tps-43-19.png
     :alt: new
   [2025-03-13] We propose a new data synthesis method, *MindGym*\ , which encourages LLMs to self-generate challenging cognitive questions, achieving superior data efficiency, cross-modality generalization, and SFT effects over SOTA baselines (e.g., *16%* gain on `MathVision <https://mathllm.github.io/mathvision/#leaderboard>`_ using only *400 samples*\ ). See more details in  `MindGym: Enhancing Vision-Language Models via Synthetic Self-Challenging Questions <https://arxiv.org/abs/2503.09499>`_.
* 
  .. image:: https://img.alicdn.com/imgextra/i4/O1CN01kUiDtl1HVxN6G56vN_!!6000000000764-2-tps-43-19.png
     :target: https://img.alicdn.com/imgextra/i4/O1CN01kUiDtl1HVxN6G56vN_!!6000000000764-2-tps-43-19.png
     :alt: new
   [2025-02-28] DJ has been integrated in `Ray's official Ecosystem <https://docs.ray.io/en/latest/ray-overview/ray-libraries.html>`_ and `Example Gallery <https://docs.ray.io/en/latest/data/examples/data_juicer_distributed_data_processing.html>`_. Besides, our patch in DJ2.0 for the streaming JSON reader has been officially integrated by `Apache Arrow <https://github.com/apache/arrow/pull/45084>`_. 
* 
  .. image:: https://img.alicdn.com/imgextra/i4/O1CN01kUiDtl1HVxN6G56vN_!!6000000000764-2-tps-43-19.png
     :target: https://img.alicdn.com/imgextra/i4/O1CN01kUiDtl1HVxN6G56vN_!!6000000000764-2-tps-43-19.png
     :alt: new
   [2025-02-27] Our work on contrastive data synthesis, `ImgDiff <https://arxiv.org/pdf/2408.04594>`_\ , has been accepted by *CVPR 2025*\ !
* 
  .. image:: https://img.alicdn.com/imgextra/i4/O1CN01kUiDtl1HVxN6G56vN_!!6000000000764-2-tps-43-19.png
     :target: https://img.alicdn.com/imgextra/i4/O1CN01kUiDtl1HVxN6G56vN_!!6000000000764-2-tps-43-19.png
     :alt: new
   [2025-02-05] We propose a new data selection method, *DaaR*\ , which is theoretically informed, via treating diversity as a reward, achieves better overall performance across 7 benchmarks when post-training SOTA LLMs. See more details in `Diversity as a Reward: Fine-Tuning LLMs on a Mixture of Domain-Undetermined Data <https://www.arxiv.org/abs/2502.04380>`_.
* 
  .. image:: https://img.alicdn.com/imgextra/i4/O1CN01kUiDtl1HVxN6G56vN_!!6000000000764-2-tps-43-19.png
     :target: https://img.alicdn.com/imgextra/i4/O1CN01kUiDtl1HVxN6G56vN_!!6000000000764-2-tps-43-19.png
     :alt: new
   [2025-01-11] We release our 2.0 paper, `Data-Juicer 2.0: Cloud-Scale Adaptive Data Processing for Foundation Models <https://arxiv.org/abs/2501.14755>`_. It now can process 70B data samples within 2.1h, using 6400 CPU cores on 50 Ray nodes from Alibaba Cloud cluster, and deduplicate 5TB data within 2.8h using 1280 CPU cores on 8 Ray nodes.
* 
  .. image:: https://img.alicdn.com/imgextra/i4/O1CN01kUiDtl1HVxN6G56vN_!!6000000000764-2-tps-43-19.png
     :target: https://img.alicdn.com/imgextra/i4/O1CN01kUiDtl1HVxN6G56vN_!!6000000000764-2-tps-43-19.png
     :alt: new
   [2025-01-03] We support post-tuning scenarios better, via 20+ related new `OPs <https://github.com/modelscope/data-juicer/releases/tag/v1.0.2>`_\ , and via unified `dataset format <https://github.com/modelscope/data-juicer/releases/tag/v1.0.3>`_ compatible to LLaMA-Factory and ModelScope-Swift.


.. raw:: html

   <details>
   <summary> History News:
   </summary>>

   - [2024-12-17] We propose *HumanVBench*, which comprises 16 human-centric tasks with synthetic data, benchmarking 22 video-MLLMs' capabilities from views of inner emotion and outer manifestations. See more details in our [paper](https://arxiv.org/abs/2412.17574), and try to [evaluate](https://github.com/modelscope/data-juicer/tree/HumanVBench) your models with it.

   - [2024-11-22] We release DJ [v1.0.0](https://github.com/modelscope/data-juicer/releases/tag/v1.0.0), in which we refactored Data-Juicer's *Operator*, *Dataset*, *Sandbox* and many other modules for better usability, such as supporting fault-tolerant, FastAPI and adaptive resource management.

   - [2024-08-25] We give a [tutorial](https://modelscope.github.io/data-juicer/_static/tutorial_kdd24.html) about data processing for multimodal LLMs in KDD'2024.

   - [2024-08-09] We propose Img-Diff, which enhances the performance of multimodal large language models through *contrastive data synthesis*, achieving a score that is 12 points higher than GPT-4V on the [MMVP benchmark](https://tsb0601.github.io/mmvp_blog/). See more details in our [paper](https://arxiv.org/abs/2408.04594), and download the dataset from [huggingface](https://huggingface.co/datasets/datajuicer/Img-Diff) and [modelscope](https://modelscope.cn/datasets/Data-Juicer/Img-Diff).
   - [2024-07-24] "Tianchi Better Synth Data Synthesis Competition for Multimodal Large Models" — Our 4th data-centric LLM competition has kicked off! Please visit the competition's [official website](https://tianchi.aliyun.com/competition/entrance/532251) for more information.
   - [2024-07-17] We utilized the Data-Juicer [Sandbox Laboratory Suite](https://github.com/modelscope/data-juicer/blob/main/docs/Sandbox) to systematically optimize data and models through a co-development workflow between data and models, achieving a new top spot on the [VBench](https://huggingface.co/spaces/Vchitect/VBench_Leaderboard) text-to-video leaderboard. The related achievements have been compiled and published in a [paper](http://arxiv.org/abs/2407.11784), and the model has been released on the [ModelScope](https://modelscope.cn/models/Data-Juicer/Data-Juicer-T2V) and [HuggingFace](https://huggingface.co/datajuicer/Data-Juicer-T2V) platforms.
   - [2024-07-12] Our *awesome list of MLLM-Data* has evolved into a systemic [survey](https://arxiv.org/abs/2407.08583) from model-data co-development perspective. Welcome to [explore](docs/awesome_llm_data) and contribute!
   - [2024-06-01] ModelScope-Sora "Data Directors" creative sprint—Our third data-centric LLM competition has kicked off! Please visit the competition's [official website](https://tianchi.aliyun.com/competition/entrance/532219) for more information.
   - [2024-03-07] We release **Data-Juicer [v0.2.0](https://github.com/alibaba/data-juicer/releases/tag/v0.2.0)** now! 
   In this new version, we support more features for **multimodal data (including video now)**, and introduce **[DJ-SORA](docs/DJ_SORA)** to provide open large-scale, high-quality datasets for SORA-like models.
   - [2024-02-20] We have actively maintained an *awesome list of LLM-Data*, welcome to [visit](docs/awesome_llm_data) and contribute!
   - [2024-02-05] Our paper has been accepted by SIGMOD'24 industrial track!
   - [2024-01-10] Discover new horizons in "Data Mixture"—Our second data-centric LLM competition has kicked off! Please visit the competition's [official website](https://tianchi.aliyun.com/competition/entrance/532174) for more information.
   - [2024-01-05] We release **Data-Juicer v0.1.3** now!
   In this new version, we support **more Python versions** (3.8-3.10), and support **multimodal** dataset [converting](tools/fmt_conversion/multimodal/README)/[processing](docs/Operators) (Including texts, images, and audios. More modalities will be supported in the future).
   Besides, our paper is also updated to [v3](https://arxiv.org/abs/2309.02033).
   - [2023-10-13] Our first data-centric LLM competition begins! Please
     visit the competition's official websites, FT-Data Ranker ([1B Track](https://tianchi.aliyun.com/competition/entrance/532157), [7B Track](https://tianchi.aliyun.com/competition/entrance/532158)), for more information.
   </details>



.. raw:: html

   <div id="table" align="center"></div>


Table of Contents
=================
* `News`_
* `Why Data-Juicer?`_
.. toctree::
   :maxdepth: 2
   :caption: User Guide

   en/DJ-cookbook
   en/Installation
   en/quick-start

* `License`_
* `Contributing`_
* `Acknowledgement`_
* `References`_

Why Data-Juicer?
----------------

:raw-html-m2r:`<img src="https://img.alicdn.com/imgextra/i2/O1CN01EteoQ31taUweAW1UE_!!6000000005918-2-tps-4034-4146.png" align="center" width="600" />`


* 
  **Systematic & Reusable**\ :
  Empowering users with a systematic library of 100+ core :doc:`OPs <docs/Operators.md>`\ , and 50+ reusable config recipes and 
  dedicated toolkits, designed to
  function independently of specific multimodal LLM datasets and processing pipelines. Supporting data analysis, cleaning, and synthesis in pre-training, post-tuning, en, zh, and more scenarios.

* 
  **User-Friendly & Extensible**\ : 
  Designed for simplicity and flexibility, with easy-start `guides <#quick-start>`_\ , and `DJ-Cookbook <#dj-cookbook>`_ containing fruitful demo usages. Feel free to `implement your own OPs <docs/DeveloperGuide#build-your-own-ops>`_ for customizable data processing.

* 
  **Efficient & Robust**\ : Providing performance-optimized `parallel data processing <docs/Distributed>`_ (Aliyun-PAI\Ray\CUDA\OP Fusion),
  faster with less resource usage, verified in large-scale production environments.


* **Effect-Proven & Sandbox**\ : Supporting data-model co-development, enabling rapid iteration
  through the :doc:`sandbox laboratory <docs/Sandbox>`\ , and providing features such as feedback loops and visualization, so that you can better understand and improve your data and models. Many effect-proven datasets and models have been derived from DJ, in scenarios such as pre-training, text-to-video and image-to-text generation.

  .. image:: https://img.alicdn.com/imgextra/i2/O1CN017U7Zz31Y7XtCJ5GOz_!!6000000003012-0-tps-3640-1567.jpg
     :target: https://img.alicdn.com/imgextra/i2/O1CN017U7Zz31Y7XtCJ5GOz_!!6000000003012-0-tps-3640-1567.jpg
     :alt: Data-in-the-loop
   

License
-------

Data-Juicer is released under Apache License 2.0.

Contributing
------------

We are in a rapidly developing field and greatly welcome contributions of new
features, bug fixes, and better documentation. Please refer to
:doc:`How-to Guide for Developers <docs/DeveloperGuide>`.

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
   :hidden:

   api

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`