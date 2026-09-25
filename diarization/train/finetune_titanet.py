"""Fine-tune TitaNet-small on meeting speakers, then export it for sherpa-onnx.

Runs on a GPU machine (Kaggle/Colab T4, or a teammate's CUDA box), not on
the Intel Mac, because NeMo needs a current PyTorch. It trains on public
data only (AMI and other open corpora); hospital audio never leaves the
hospital. Not yet run end to end: check the first epoch's loss before
leaving it alone.

  pip install "nemo_toolkit[asr]" onnx
  python finetune_titanet.py --train ami_train.jsonl --val ami_val.jsonl --epochs 10

Follows NeMo's own speaker fine-tuning recipe: take the pretrained
titanet_small config, size the classifier to our training speakers, build
the model, then load every pretrained weight except the old classifier
(`decoder.final`). The export carries the same metadata keys as the stock
sherpa-onnx model, so the file drops into diarization/models/.
"""

import argparse
import json

import lightning.pytorch as pl
import nemo.collections.asr as nemo_asr
import onnx
from omegaconf import OmegaConf, open_dict


def add_meta(filename, meta):
    model = onnx.load(filename)
    for k, v in meta.items():
        p = model.metadata_props.add()
        p.key, p.value = k, str(v)
    onnx.save(model, filename)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True)
    ap.add_argument("--val", required=True)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--out", default="nemo_en_titanet_small_ft.onnx")
    a = ap.parse_args()

    labels = sorted({json.loads(line)["label"] for line in open(a.train)})
    cfg = nemo_asr.models.EncDecSpeakerLabelModel.from_pretrained("titanet_small", return_config=True)
    with open_dict(cfg):
        for split, path, shuffle in (("train_ds", a.train, True), ("validation_ds", a.val, False)):
            cfg[split].manifest_filepath = path
            cfg[split].labels = labels
            cfg[split].batch_size = a.batch
            cfg[split].shuffle = shuffle
        cfg.decoder.num_classes = len(labels)
        cfg.optim.lr = a.lr

    trainer = pl.Trainer(max_epochs=a.epochs, accelerator="gpu", devices=1,
                         precision="16-mixed", log_every_n_steps=20)
    model = nemo_asr.models.EncDecSpeakerLabelModel(cfg=cfg, trainer=trainer)
    model.maybe_init_from_pretrained_checkpoint(OmegaConf.create({
        "init_from_pretrained_model": {"titanet": {"name": "titanet_small", "exclude": ["decoder.final"]}}}))
    trainer.fit(model)

    model.eval()
    model.export(a.out)
    pre = cfg.preprocessor
    add_meta(a.out, {
        "framework": "nemo",
        "language": "multilingual meetings (fine-tuned)",
        "url": "https://catalog.ngc.nvidia.com/orgs/nvidia/teams/nemo/models/titanet_small",
        "comment": f"TitaNet-small fine-tuned on {len(labels)} meeting speakers",
        "sample_rate": pre.sample_rate,
        "output_dim": cfg.decoder.emb_sizes,
        "feature_normalize_type": pre.normalize,
        "window_size_ms": int(float(pre.window_size) * 1000),
        "window_stride_ms": int(float(pre.window_stride) * 1000),
        "window_type": pre.window,
        "feat_dim": pre.features,
    })
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
