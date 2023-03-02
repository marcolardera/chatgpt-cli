# ChatGPT CLI

![Screenshot](screenshot.png)

## Overview

Simple script for chatting with ChatGPT from the command line, using the official API ([Released March 1st, 2023](https://openai.com/blog/introducing-chatgpt-and-whisper-apis)). It allows, after providing a valid API Key, to use ChatGPT at the maximum speed, at a fraction of the cost of a full ChatGPT Plus subscription (at least for the average user).

## How to get an API Key

Go to [platform.openai.com](platform.openai.com) and log-in with your OpenAI account (register if you don't have one). Click on your name initial in the top-right corner, then select *"View API keys"*. Finally click on *"Create new secret key"*. That's it.

You may also need to add a payment method, clicking on *Billing --> Payment methods*. New accounts should have some free credits, but adding a payment method may still be mandatory. For pricing, check [this page](https://openai.com/pricing).

## Installation and configuration

You need Python installed on your system.

Install the dependencies:

`pip install -r requirements.txt`

After that, edit the *config.yaml* file, putting your API Key as the value of the "api-key" parameter. Save the file.

## Usage

Launch the *"chatgpt.py"* script (depending on your environment you may need to use the "python3" command instead of "python"):

`python chatgpt.py`

Then just chat! Use the `/q` command to quit.

