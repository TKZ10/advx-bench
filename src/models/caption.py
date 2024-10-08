import os

import requests
import torch
from PIL import Image

os.environ["TOKENIZERS_PARALLELISM"] = "true"

try:
    from .utils import get_device
except ImportError:
    from utils import get_device


"""
models
"""


def caption_llama3(img: Image.Image) -> list[str]:
    # best model for gpu
    assert torch.cuda.is_available(), "GPU not available"
    from transformers import AutoModel, AutoTokenizer

    model = AutoModel.from_pretrained("openbmb/MiniCPM-Llama3-V-2_5", trust_remote_code=True, torch_dtype=torch.float16)
    model = model.to(device="cuda")

    tokenizer = AutoTokenizer.from_pretrained("openbmb/MiniCPM-Llama3-V-2_5", trust_remote_code=True)
    model.eval()

    image = Image.open("xx.jpg").convert("RGB")
    question = "What is in the image?"
    msgs = [{"role": "user", "content": question}]

    res = model.chat(
        image=image,
        msgs=msgs,
        tokenizer=tokenizer,
        sampling=True,  # if sampling=False, beam_search will be used by default
        temperature=0.7,
        # system_prompt='' # pass system_prompt if needed
    )
    assert isinstance(res, list)
    return res


def caption_blip(img: Image.Image) -> list[str]:
    # best model for cpu
    from transformers import BlipForConditionalGeneration, BlipProcessor

    device = get_device()
    model_id = "Salesforce/blip-image-captioning-large"
    processor = BlipProcessor.from_pretrained(model_id, clean_up_tokenization_spaces=True)
    model = BlipForConditionalGeneration.from_pretrained(model_id).to(device)

    img = img.convert("RGB")
    inputs = processor(img, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    out = model.generate(**inputs, max_new_tokens=30)
    res = processor.decode(out[0], skip_special_tokens=True, clean_up_tokenization_spaces=True)

    assert isinstance(res, str)
    return get_noun_chunks(res)


def caption_gpt2(img: Image.Image) -> list[str]:
    from transformers import pipeline

    device = get_device()
    image_to_text = pipeline("image-to-text", model="nlpconnect/vit-gpt2-image-captioning", device=device)
    img = img.convert("RGB")
    res = image_to_text(img)[0]["generated_text"]

    assert isinstance(res, str)
    return get_noun_chunks(res)


def caption_blipvqa(img: Image.Image) -> list[str]:
    from transformers import BlipForQuestionAnswering, BlipProcessor

    device = get_device()
    model_id = "Salesforce/blip-vqa-capfilt-large"
    processor = BlipProcessor.from_pretrained(model_id, clean_up_tokenization_spaces=True)
    model = BlipForQuestionAnswering.from_pretrained(model_id).to(device)

    question = "What is in the image?"
    img = img.convert("RGB")
    inputs = processor(img, question, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    out = model.generate(**inputs, max_new_tokens=30)
    res = processor.decode(out[0], skip_special_tokens=True, clean_up_tokenization_spaces=True)

    assert isinstance(res, str)
    return get_noun_chunks(res)


"""
utils
"""


def get_noun_chunks(sentence: str) -> list[str]:
    # python -m spacy download en_core_web_sm
    import spacy

    nlp = spacy.load("en_core_web_sm")
    doc = nlp(sentence)
    noun_chunks = [chunk.text for chunk in doc.noun_chunks]
    noun_chunks = list(set(noun_chunks))
    return noun_chunks


"""
example usage
"""


if __name__ == "__main__":
    url = "http://images.cocodataset.org/val2017/000000039769.jpg"
    img = Image.open(requests.get(url, stream=True).raw)

    text_query = caption_gpt2(img)
    print(text_query)

    text_query = caption_blip(img)
    print(text_query)
