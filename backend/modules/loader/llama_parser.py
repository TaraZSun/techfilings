import os
import llama_parser

def parse_filings_to_markdown(filings_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in os.listdir(filings_dir):
        if filename.endswith('.txt'):
            input_path = os.path.join(filings_dir, filename)
            output_path = os.path.join(output_dir, filename.replace('.txt', '.md'))

            with open(input_path, 'r') as infile:
                text = infile.read()

            markdown = llama_parser.parse_to_markdown(text)

            with open(output_path, 'w') as outfile:
                outfile.write(markdown)