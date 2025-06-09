import sys
import os
import torch
import cv2
import numpy as np
from PIL import Image
from torchvision.transforms import ToTensor, ToPILImage
from NAFNet import NAFNet

print("Current working directory:", os.getcwd())

# Initialize the model with required parameters
model = NAFNet(img_channel=3, width=64, enc_blk_nums=[1, 2, 8, 8], dec_blk_nums=[1, 1, 1, 1])
model.load_state_dict(torch.load('weights/NAFNet-GoPro-width64.pth', map_location='cpu'), strict=False)
model.eval()

# Load and preprocess image
def preprocess_image(image_path):
    img = cv2.imread(image_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = ToTensor()(Image.fromarray(img)).unsqueeze(0)  # Shape: [1, C, H, W]
    return img

def postprocess_image(tensor):
    img = ToPILImage()(tensor.squeeze(0).clamp(0, 1))  # Clamp values to valid range
    return np.array(img) 
# jajal en ndelok
# Path to input image
input_path = "sample/blurry_australiantaxinvoicetemplate.webp"  # Ensure correct file extension
output_path = "output_sharp.jpg"

# Process
input_image = preprocess_image(input_path)
with torch.no_grad():
    output_image = model(input_image)

# Save result
sharp_image = postprocess_image(output_image)
cv2.imwrite(output_path, cv2.cvtColor(sharp_image, cv2.COLOR_RGB2BGR))