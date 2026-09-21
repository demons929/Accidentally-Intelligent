from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import torch
from sklearn.model_selection import train_test_split
from torch.utils.data import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

from config import get_settings
from pipeline import CANONICAL_CATEGORIES


class EmailDataset(Dataset):
    def __init__(self, texts: list[str], labels: list[int], tokenizer, max_length: int) -> None:
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, index: int) -> dict:
        encoded = self.tokenizer(
            self.texts[index],
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        item = {key: value.squeeze(0) for key, value in encoded.items()}
        item["labels"] = torch.tensor(self.labels[index], dtype=torch.long)
        return item


def train(csv_path: Path, output_dir: Path) -> None:
    settings = get_settings()
    frame = pd.read_csv(csv_path)
    if not {"text", "label"}.issubset(frame.columns):
        raise ValueError("Training CSV must contain 'text' and 'label' columns")

    label2id = {label: index for index, label in enumerate(CANONICAL_CATEGORIES)}
    id2label = {index: label for label, index in label2id.items()}
    labels = frame["label"].map(label2id)
    if labels.isna().any():
        bad = sorted(set(frame.loc[labels.isna(), "label"]))
        raise ValueError(f"Unknown labels found: {bad}")

    train_texts, val_texts, train_labels, val_labels = train_test_split(
        frame["text"].astype(str).tolist(),
        labels.astype(int).tolist(),
        test_size=0.15,
        random_state=42,
        stratify=labels.astype(int).tolist() if labels.nunique() > 1 else None,
    )

    tokenizer = AutoTokenizer.from_pretrained("roberta-base")
    model = AutoModelForSequenceClassification.from_pretrained(
        "roberta-base",
        num_labels=len(CANONICAL_CATEGORIES),
        label2id=label2id,
        id2label=id2label,
    )

    args = TrainingArguments(
        output_dir=str(output_dir),
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=2e-5,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        num_train_epochs=3,
        weight_decay=0.01,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
    )
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=EmailDataset(train_texts, train_labels, tokenizer, settings.max_sequence_length),
        eval_dataset=EmailDataset(val_texts, val_labels, tokenizer, settings.max_sequence_length),
        tokenizer=tokenizer,
    )
    trainer.train()
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=get_settings().train_dir / "train.csv", help="CSV with text,label columns")
    parser.add_argument("--output-dir", type=Path, default=get_settings().model_dir)
    parsed = parser.parse_args()
    if not parsed.csv.exists():
        raise FileNotFoundError(
            f"Training data not found at {parsed.csv}. "
            "Create data/train/train.csv with text,label columns or pass --csv."
        )
    train(parsed.csv, parsed.output_dir)
