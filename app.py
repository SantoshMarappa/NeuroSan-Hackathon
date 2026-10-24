import gradio as gr
import requests

API_URL = (
    "http://localhost:8080/api/v1/"
    "basic/book_recommender/streaming_chat"
)


def recommend_books(user_message):

    payload = {
        "message": user_message
    }

    result = []

    try:
        with requests.post(
            API_URL,
            json=payload,
            stream=True,
            timeout=60
        ) as response:

            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):

                if not line:
                    continue

                result.append(f"RAW: {line}")

            return "\n".join(result)

    except Exception as e:
        return str(e)


with gr.Blocks(title="Book Recommender") as demo:

    gr.Markdown("# 📚 Book Recommender")

    user_input = gr.Textbox(
        label="Describe the type of book you're looking for",
        placeholder="Recommend science fiction books with space exploration...",
        lines=3
    )

    submit_btn = gr.Button("Get Recommendations")

    output = gr.Textbox(
        label="Recommendations",
        lines=15
    )

    submit_btn.click(
        fn=recommend_books,
        inputs=user_input,
        outputs=output
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)