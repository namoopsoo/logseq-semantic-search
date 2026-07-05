
import numpy as np
import itertools
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim

hugging_face_cache = "/models"
MODEL_NAME = "all-MiniLM-L6-v2"
MODEL_NAME = "all-mpnet-base-v2"
MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B" 

model = SentenceTransformer(
  local_files_only=True,
  model_name_or_path=MODEL_NAME,
  cache_folder=hugging_face_cache)

query1 = "going to the beach to go collect some boats, some sand in my shoes, checkout how many metal detector people there are, maybe get a sun tan. Hopefully will not forget the sunscreen."
query2 = "there was that movie about a castaway stranded on a beach, I think Tom Hanks, he had a volleyball that was his friend. Maybe did he find other peoples messages in bottles on the shore or throw his own messages into the ocean. I dont remember. For sure there were coconuts. "
query3 = "there is a lot going on in the sculpture park today. People going to do yoga looks like. Nice day. Trees, shade. There is traffic though, from cars piling up to go shopping at the wholesale grocery store."
mutual_embeddings = []

array = np.zeros(shape=(3,3))
for [[i, one ], [j, two]] in itertools.combinations([[0, query1], [1, query2], [2, query3]], 2):
    mutual_embeddings = model.encode([one, two], normalize_embeddings=True).tolist()
    array[i, j] = cos_sim(mutual_embeddings[0], mutual_embeddings[1])

print(array)
print("ok bye")
