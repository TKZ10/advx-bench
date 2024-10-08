import requests
from PIL import Image
from transformers import BlipForConditionalGeneration, BlipProcessor

processor = BlipProcessor.from_pretrained("moranyanuka/blip-image-captioning-large-mocha")
model = BlipForConditionalGeneration.from_pretrained("moranyanuka/blip-image-captioning-large-mocha")

img_url = "https://storage.googleapis.com/sfr-vision-language-research/BLIP/demo.jpg"
raw_image = Image.open(requests.get(img_url, stream=True).raw).convert("RGB")

# # conditional image captioning
text = "a photography of"
inputs = processor(raw_image, text, return_tensors="pt")
out = model.generate(**inputs)
print(processor.decode(out[0], skip_special_tokens=True))

# unconditional image captioning
# inputs = processor(raw_image, return_tensors="pt")
# out = model.generate(**inputs)
# print(processor.decode(out[0], skip_special_tokens=True))
