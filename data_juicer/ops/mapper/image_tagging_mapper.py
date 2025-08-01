from collections import Counter

import numpy as np

from data_juicer.utils.constant import Fields, MetaKeys
from data_juicer.utils.mm_utils import load_data_with_context, load_image
from data_juicer.utils.model_utils import get_model, prepare_model, ram, torch

from ..base_op import OPERATORS, TAGGING_OPS, UNFORKABLE, Mapper
from ..op_fusion import LOADED_IMAGES

OP_NAME = "image_tagging_mapper"


@TAGGING_OPS.register_module(OP_NAME)
@UNFORKABLE.register_module(OP_NAME)
@OPERATORS.register_module(OP_NAME)
@LOADED_IMAGES.register_module(OP_NAME)
class ImageTaggingMapper(Mapper):
    """Mapper to generate image tags."""

    _accelerator = "cuda"

    def __init__(self, tag_field_name: str = MetaKeys.image_tags, *args, **kwargs):
        """
        Initialization method.
        :param tag_field_name: the field name to store the tags. It's
            "image_tags" in default.
        :param args: extra args
        :param kwargs: extra args
        """
        kwargs.setdefault("mem_required", "9GB")
        super().__init__(*args, **kwargs)
        self.model_key = prepare_model(
            model_type="recognizeAnything", pretrained_model_name_or_path="ram_plus_swin_large_14m.pth", input_size=384
        )
        self.transform = ram.get_transform(image_size=384)
        self.tag_field_name = tag_field_name

    def process_single(self, sample, rank=None, context=False):
        # check if it's generated already
        if self.tag_field_name in sample[Fields.meta]:
            return sample

        # there is no image in this sample
        if self.image_key not in sample or not sample[self.image_key]:
            sample[Fields.meta][self.tag_field_name] = np.array([[]], dtype=np.str_)
            return sample

        # load images
        loaded_image_keys = sample[self.image_key]
        sample, images = load_data_with_context(
            sample, context, loaded_image_keys, load_image, mm_bytes_key=self.image_bytes_key
        )

        model = get_model(self.model_key, rank, self.use_cuda())
        image_tags = []
        for _, value in enumerate(loaded_image_keys):
            image = images[value]

            image_tensor = torch.unsqueeze(self.transform(image), dim=0).to(next(model.parameters()).device)
            with torch.no_grad():
                tags, _ = model.generate_tag(image_tensor)

            words = [word.strip() for word in tags[0].split("|")]
            word_count = Counter(words)
            sorted_word_list = [item for item, _ in word_count.most_common()]
            image_tags.append(np.array(sorted_word_list, dtype=np.str_))

        sample[Fields.meta][self.tag_field_name] = image_tags
        return sample
