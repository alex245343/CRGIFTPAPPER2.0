import os
from PIL import Image, ImageDraw, ImageEnhance
from flask import Flask, request, jsonify, send_file
import config
import io

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def load_images(image_paths):
    images = []
    for path in image_paths:
        img = Image.open(path)
        images.append(img)
    return images

def load_background_image(path, background_color=None):
    if path:
        return Image.open(path)
    return Image.new('RGB', (config.A4_WIDTH, config.A4_HEIGHT), background_color or 'white')

def crop_to_circle(img):
    size = min(img.size)
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    img_cropped = img.crop((0, 0, size, size))
    img_circular = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img_circular.paste(img_cropped, (0, 0), mask)
    return img_circular

def enhance_image(img, brightness_factor, contrast_factor, saturation_factor, sharpness_factor):
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(brightness_factor)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(contrast_factor)
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(saturation_factor)
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(sharpness_factor)
    return img

def create_a4_collage(images, background_image, output_filename=None, background_color=None):
    collage = Image.new('RGB', (config.A4_WIDTH, config.A4_HEIGHT), background_color or 'white')
    background_image = background_image.resize((config.A4_WIDTH, config.A4_HEIGHT), Image.LANCZOS)
    background_image = enhance_image(background_image, config.BRIGHTNESS, config.CONTRAST, config.SATURATION, config.SHARPNESS)
    collage.paste(background_image, (0, 0))
    
    img_width = (config.A4_WIDTH - (config.SPACING * (config.NUM_COLS + 1))) // config.NUM_COLS
    img_height = (config.A4_HEIGHT - (config.SPACING * (config.NUM_ROWS + 1))) // config.NUM_ROWS
    
    for i in range(config.NUM_ROWS):
        for j in range(config.NUM_COLS):
            img_index = (i * config.NUM_COLS + j) % len(images)
            img = images[img_index].copy()
            
            img_aspect_ratio = img.width / img.height
            
            if img_aspect_ratio > img_width / img_height:
                new_height = img_height
                new_width = int(new_height * img_aspect_ratio)
                img = img.resize((new_width, new_height), Image.LANCZOS)
                left = (new_width - img_width) // 2
                img = img.crop((left, 0, left + img_width, new_height))
            else:
                new_width = img_width
                new_height = int(new_width / img_aspect_ratio)
                img = img.resize((new_width, new_height), Image.LANCZOS)
                top = (new_height - img_height)
                img = img.crop((0, top, new_width, top + img_height))

            if config.CIRCULAR_CROP.lower() == 'yes':
                img = crop_to_circle(img)
                mask = img.split()[3]
            else:
                img = img.convert("RGB")
                mask = None

            img = enhance_image(img, config.BRIGHTNESS, config.CONTRAST, config.SATURATION, config.SHARPNESS)

            x = j * (img_width + config.SPACING) + config.SPACING
            y = i * (img_height + config.SPACING) + config.SPACING
            collage.paste(img, (x, y), mask if mask else None)

    if output_filename:
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_filename)
        collage.save(output_path)
        return output_path
    else:
        img_byte_arr = io.BytesIO()
        collage.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr

@app.route('/MrPapper/update_config', methods=['POST'])
def update_config():
    data = request.json
    config.NUM_ROWS = int(float(data.get('rows', config.NUM_ROWS)) * 10)
    config.NUM_COLS = int(float(data.get('cols', config.NUM_COLS)) * 10)
    config.SPACING = int(float(data.get('spacing', config.SPACING)) * 100)
    config.BRIGHTNESS = float(data.get('brightness', config.BRIGHTNESS)) * 2
    config.CONTRAST = float(data.get('contrast', config.CONTRAST)) * 2
    config.SATURATION = float(data.get('saturation', config.SATURATION)) * 2
    config.SHARPNESS = float(data.get('sharpness', config.SHARPNESS)) * 2
    config.CIRCULAR_CROP = data.get('clip_shape', config.CIRCULAR_CROP)
    config.IMAGE_PATHS = data.get('image_paths', config.IMAGE_PATHS)
    config.BACKGROUND_IMAGE_PATH = data.get('background_path', config.BACKGROUND_IMAGE_PATH)
    background_color = data.get('background_color')

    if config.IMAGE_PATHS:
        images = load_images(config.IMAGE_PATHS)
        background_image = load_background_image(config.BACKGROUND_IMAGE_PATH, background_color)
        preview = create_a4_collage(images, background_image, background_color=background_color)
        return send_file(preview, mimetype='image/png')
    return jsonify({"status": "success"})

@app.route('/MrPapper/upload_files', methods=['POST'])
def upload_files():
    photos = request.files.getlist('photos')
    background = request.files.get('background')
    paths = []

    if photos:
        config.IMAGE_PATHS = []
        for photo in photos:
            filename = photo.filename
            path = os.path.join(UPLOAD_FOLDER, filename)
            photo.save(path)
            config.IMAGE_PATHS.append(path)
        paths = config.IMAGE_PATHS

    if background:
        filename = background.filename
        path = os.path.join(UPLOAD_FOLDER, filename)
        background.save(path)
        config.BACKGROUND_IMAGE_PATH = path

    return jsonify({
        "status": "success",
        "paths": paths if photos else [],
        "path": config.BACKGROUND_IMAGE_PATH if background else ''
    })

@app.route('/MrPapper/generate_collage', methods=['POST'])
def generate_collage():
    data = request.json or {}
    background_color = data.get('background_color')
    images = load_images(config.IMAGE_PATHS)
    background_image = load_background_image(config.BACKGROUND_IMAGE_PATH, background_color)
    output_path = create_a4_collage(images, background_image, 'collage_a4.png', background_color=background_color)
    return send_file(output_path, mimetype='image/png')

@app.route('/MrPapper')
def serve_html():
    return app.send_static_file('index.html')

if __name__ == "__main__":
    app.static_folder = '.'
    app.run(debug=True, port=5000)