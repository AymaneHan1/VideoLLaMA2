import spaces

import os
import re

import torch
import gradio as gr

import sys
sys.path.append('./')
from videollama2 import model_init, mm_infer
from videollama2.utils import disable_torch_init
from videollama2.mm_utils import disable_flash_attention_2


title_markdown = ("""
<div style="display: flex; justify-content: center; align-items: center; text-align: center;">
  <a href="https://github.com/DAMO-NLP-SG/VideoLLaMA2" style="margin-right: 20px; text-decoration: none; display: flex; align-items: center;">
    <img src="https://s2.loli.net/2024/06/03/D3NeXHWy5az9tmT.png" alt="VideoLLaMA 2 🔥🚀🔥" style="max-width: 120px; height: auto;">
  </a>
  <div>
    <h1 >VideoLLaMA 2: Advancing Spatial-Temporal Modeling and Audio Understanding in Video-LLMs</h1>
    <h5 style="margin: 0;">If this demo please you, please give us a star ⭐ on Github or 💖 on this space.</h5>
  </div>
</div>


<div align="center">
    <div style="display:flex; gap: 0.25rem; margin-top: 10px;" align="center">
        <a href="https://github.com/DAMO-NLP-SG/VideoLLaMA2"><img src='https://img.shields.io/badge/Github-VideoLLaMA2-9C276A'></a>
        <a href="https://arxiv.org/pdf/2406.07476.pdf"><img src="https://img.shields.io/badge/Arxiv-2406.07476-AD1C18"></a>
        <a href="https://github.com/DAMO-NLP-SG/VideoLLaMA2/stargazers"><img src="https://img.shields.io/github/stars/DAMO-NLP-SG/VideoLLaMA2.svg?style=social"></a>
    </div>
</div>
""")


block_css = """
#buttons button {
    min-width: min(120px,100%);
    color: #9C276A
}
"""


tos_markdown = ("""
### Terms of use
By using this service, users are required to agree to the following terms:
The service is a research preview intended for non-commercial use only. It only provides limited safety measures and may generate offensive content. It must not be used for any illegal, harmful, violent, racist, or sexual purposes. The service may collect user dialogue data for future research.
Please click the "Flag" button if you get any inappropriate answer! We will collect those to keep improving our moderator.
For an optimal experience, please use desktop computers for this demo, as mobile devices may compromise its quality.
""")


learn_more_markdown = ("""
### License
This project is released under the Apache 2.0 license as found in the LICENSE file. The service is a research preview intended for non-commercial use ONLY, subject to the model Licenses of LLaMA and Mistral, Terms of Use of the data generated by OpenAI, and Privacy Practices of ShareGPT. Please get in touch with us if you find any potential violations.
""")


plum_color = gr.themes.colors.Color(
    name='plum',
    c50='#F8E4EF',
    c100='#E9D0DE',
    c200='#DABCCD',
    c300='#CBA8BC',
    c400='#BC94AB',
    c500='#AD809A',
    c600='#9E6C89',
    c700='#8F5878',
    c800='#804467',
    c900='#713056',
    c950='#662647',
)


class Chat:

    def __init__(self, model_path, load_8bit=False, load_4bit=False):
        disable_torch_init()

        self.model, self.processor, self.tokenizer = model_init(model_path, load_8bit=load_8bit, load_4bit=load_4bit)

    @spaces.GPU(duration=120)
    @torch.inference_mode()
    def generate(self, data: list, message, temperature, top_p, max_output_tokens):
        # TODO: support multiple turns of conversation.
        assert len(data) == 1

        tensor, modal = data[0]
        response = mm_infer(tensor, message, self.model, self.tokenizer, modal=modal.strip('<>'), 
            do_sample=True if temperature > 0.0 else False,
            temperature=temperature,
            top_p=top_p,
            max_new_tokens=max_output_tokens)

        return response


@spaces.GPU(duration=120)
def generate(image, video, message, chatbot, textbox_in, temperature, top_p, max_output_tokens, dtype=torch.float16):
    data = []

    processor = handler.processor
    try:
        if image is not None:
            data.append((processor['image'](image).to(handler.model.device, dtype=dtype), '<image>'))
        elif video is not None:
            data.append((processor['video'](video).to(handler.model.device, dtype=dtype), '<video>'))
        elif image is None and video is None:
            data.append((None, '<text>'))
        else:
            raise NotImplementedError("Not support image and video at the same time")
    except Exception as e:
        traceback.print_exc()
        return gr.update(value=None, interactive=True), gr.update(value=None, interactive=True), message, chatbot

    assert len(message) % 2 == 0, "The message should be a pair of user and system message."

    show_images = ""
    if image is not None:
        show_images += f'<img src="./file={image}" style="display: inline-block;width: 250px;max-height: 400px;">'
    if video is not None:
        show_images += f'<video controls playsinline width="500" style="display: inline-block;"  src="./file={video}"></video>'

    one_turn_chat = [textbox_in, None]

    # 1. first run case
    if len(chatbot) == 0:
        one_turn_chat[0] += "\n" + show_images
    # 2. not first run case
    else:
        # scanning the last image or video
        length = len(chatbot)
        for i in range(length - 1, -1, -1):
            previous_image = re.findall(r'<img src="./file=(.+?)"', chatbot[i][0])
            previous_video = re.findall(r'<video controls playsinline width="500" style="display: inline-block;"  src="./file=(.+?)"', chatbot[i][0])

            if len(previous_image) > 0:
                previous_image = previous_image[-1]
                # 2.1 new image append or pure text input will start a new conversation
                if (video is not None) or (image is not None and os.path.basename(previous_image) != os.path.basename(image)):
                    message.clear()
                    one_turn_chat[0] += "\n" + show_images
                break
            elif len(previous_video) > 0:
                previous_video = previous_video[-1]
                # 2.2 new video append or pure text input will start a new conversation
                if image is not None or (video is not None and os.path.basename(previous_video) != os.path.basename(video)):
                    message.clear()
                    one_turn_chat[0] += "\n" + show_images
                break

    message.append({'role': 'user', 'content': textbox_in})
    text_en_out = handler.generate(data, message, temperature=temperature, top_p=top_p, max_output_tokens=max_output_tokens)
    message.append({'role': 'assistant', 'content': text_en_out})

    one_turn_chat[1] = text_en_out
    chatbot.append(one_turn_chat)

    return gr.update(value=image, interactive=True), gr.update(value=video, interactive=True), message, chatbot


def regenerate(message, chatbot):
    message.pop(-1), message.pop(-1)
    chatbot.pop(-1)
    return message, chatbot


def clear_history(message, chatbot):
    message.clear(), chatbot.clear()
    return (gr.update(value=None, interactive=True),
            gr.update(value=None, interactive=True),
            message, chatbot,
            gr.update(value=None, interactive=True))


# BUG of Zero Environment
# 1. The environment is fixed to torch>=2.0,<=2.2, gradio>=4.x.x
# 2. The operation or tensor which requires cuda are limited in those functions wrapped via spaces.GPU
# 3. The function can't return tensor or other cuda objects.

model_path = 'DAMO-NLP-SG/VideoLLaMA2.1-7B-16F'

# Ensure Flash Attention 2.0 is disabled
disable_flash_attention_2()

handler = Chat(model_path, load_8bit=False, load_4bit=True)

textbox = gr.Textbox(show_label=False, placeholder="Enter text and press ENTER", container=False)

theme = gr.themes.Default(primary_hue=plum_color)
# theme.update_color("primary", plum_color.c500)
theme.set(slider_color="#9C276A")
theme.set(block_title_text_color="#9C276A")
theme.set(block_label_text_color="#9C276A")
theme.set(button_primary_text_color="#9C276A")
# theme.set(button_secondary_text_color="*neutral_800")


with gr.Blocks(title='VideoLLaMA 2 🔥🚀🔥', theme=theme, css=block_css) as demo:
    gr.Markdown(title_markdown)
    message = gr.State([])

    with gr.Row():
        with gr.Column(scale=3):
            image = gr.Image(label="Input Image", type="filepath")
            video = gr.Video(label="Input Video")

            with gr.Accordion("Parameters", open=True) as parameter_row:
                # num_beams = gr.Slider(
                #     minimum=1,
                #     maximum=10,
                #     value=1,
                #     step=1,
                #     interactive=True,
                #     label="beam search numbers",
                # )

                temperature = gr.Slider(
                    minimum=0.1,
                    maximum=1.0,
                    value=0.2,
                    step=0.1,
                    interactive=True,
                    label="Temperature",
                )

                top_p = gr.Slider(
                        minimum=0.0,
                        maximum=1.0,
                        value=0.7,
                        step=0.1,
                        interactive=True,
                        label="Top P",
                )

                max_output_tokens = gr.Slider(
                    minimum=64,
                    maximum=1024,
                    value=512,
                    step=64,
                    interactive=True,
                    label="Max output tokens",
                )

        with gr.Column(scale=7):
            chatbot = gr.Chatbot(label="VideoLLaMA 2", bubble_full_width=True, height=750)
            with gr.Row():
                with gr.Column(scale=8):
                    textbox.render()
                with gr.Column(scale=1, min_width=50):
                    submit_btn = gr.Button(value="Send", variant="primary", interactive=True)
            with gr.Row(elem_id="buttons") as button_row:
                upvote_btn     = gr.Button(value="👍  Upvote", interactive=True)
                downvote_btn   = gr.Button(value="👎  Downvote", interactive=True)
                # flag_btn     = gr.Button(value="⚠️  Flag", interactive=True)
                # stop_btn     = gr.Button(value="⏹️  Stop Generation", interactive=False)
                regenerate_btn = gr.Button(value="🔄  Regenerate", interactive=True)
                clear_btn      = gr.Button(value="🗑️  Clear history", interactive=True)

    with gr.Row():
        with gr.Column():
            cur_dir = os.path.dirname(os.path.abspath(__file__))
            gr.Examples(
                examples=[
                    [
                        f"{cur_dir}/examples/extreme_ironing.jpg",
                        "What happens in this image?",
                    ],
                    [
                        f"{cur_dir}/examples/waterview.jpg",
                        "What are the things I should be cautious about when I visit here?",
                    ],
                    [
                        f"{cur_dir}/examples/desert.jpg",
                        "If there are factual errors in the questions, point it out; if not, proceed answering the question. What’s happening in the desert?",
                    ],
                ],
                inputs=[image, textbox],
            )
        with gr.Column():
            gr.Examples(
                examples=[
                    [
                        f"{cur_dir}/../../assets/cat_and_chicken.mp4",
                        "What happens in this video?",
                    ],
                    [
                        f"{cur_dir}/../../assets/sora.mp4",
                        "Please describe this video.",
                    ],
                    [
                        f"{cur_dir}/examples/sample_demo_1.mp4",
                        "What does the baby do?",
                    ],
                ],
                inputs=[video, textbox],
            )

    gr.Markdown(tos_markdown)
    gr.Markdown(learn_more_markdown)

    submit_btn.click(
        generate, 
        [image, video, message, chatbot, textbox, temperature, top_p, max_output_tokens],
        [image, video, message, chatbot])

    regenerate_btn.click(
        regenerate, 
        [message, chatbot], 
        [message, chatbot]).then(
        generate, 
        [image, video, message, chatbot, textbox, temperature, top_p, max_output_tokens], 
        [image, video, message, chatbot])

    clear_btn.click(
        clear_history, 
        [message, chatbot],
        [image, video, message, chatbot, textbox])

demo.launch()
