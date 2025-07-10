from transformers import (
    Wav2Vec2Processor,
)
import torch.nn as nn
import torch
import numpy as np
from transformers.models.wav2vec2.modeling_wav2vec2 import Wav2Vec2Model, Wav2Vec2PreTrainedModel

class RegressionHead(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.dense = nn.Linear(config.hidden_size, config.hidden_size)
        self.dropout = nn.Dropout(config.final_dropout)
        self.out_proj = nn.Linear(config.hidden_size, config.num_labels)

    def forward(self, features, **kwargs):
        x = self.dropout(features)
        x = self.dense(x)
        x = torch.tanh(x)
        x = self.dropout(x)
        return self.out_proj(x)

class EmotionModel(Wav2Vec2PreTrainedModel):
    def __init__(self, config):
        super().__init__(config)
        self.config = config
        self.wav2vec2 = Wav2Vec2Model(config)
        self.classifier = RegressionHead(config)
        self.init_weights()

    def forward(self, input_values):
        outputs = self.wav2vec2(input_values)
        hidden_states = outputs[0]
        pooled = torch.mean(hidden_states, dim=1)
        logits = self.classifier(pooled)
        return pooled, logits


def load_emotion_model(model_name='audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim', device='cpu'):
    processor = Wav2Vec2Processor.from_pretrained(model_name)
    model = EmotionModel.from_pretrained(model_name).to(device)
    return processor, model

def extract_emotions(audios, output_files, model, processor, device='cpu'):
    results = []

    for audio in audios:
        waveform = audio.waveform  # Expected to be a 1D NumPy array
        sr = audio.sampling_rate

        processed = processor(waveform, sampling_rate=sr, return_tensors="pt", padding=True)
        input_values = processed['input_values'].to(device)

        with torch.no_grad():
            _, logits = model(input_values)
            scores = logits.cpu().numpy()[0].tolist()

        results.append({
            "arousal": scores[0],
            "dominance": scores[1],
            "valence": scores[2]
        })

    return results  # optionally write to output_files if needed

