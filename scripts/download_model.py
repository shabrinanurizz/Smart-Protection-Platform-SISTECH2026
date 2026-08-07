import os
import gdown

MODEL_PATH = "model_registry/v1/model.pkl.bz2"
FILE_ID = "1veOSma_SAA8zrSwlOG2cbLcnAjKg88QL"

def download_model():
    if os.path.exists(MODEL_PATH):
        print("Model sudah ada")
        return

    os.makedirs(
        os.path.dirname(MODEL_PATH),
        exist_ok=True
    )

    gdown.download(
        id=FILE_ID,
        output=MODEL_PATH,
        quiet=False
    )

if __name__ == "__main__":
    download_model()