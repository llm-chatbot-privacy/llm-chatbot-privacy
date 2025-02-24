
import json
import boto3
from datetime import datetime
import os
import openai
from openai import OpenAIError, RateLimitError, Timeout
import time
import logging


print(OpenAIError.__bases__)
print(RateLimitError.__bases__)
print(Timeout.__bases__)