from datetime import datetime

decorrido = 745476177629  # timestamp em milissegundos

date = datetime.fromtimestamp(decorrido / 1000)

print(date.strftime("%Y-%m-%d %H:%M:%S"))
print("Data e hora:", date)