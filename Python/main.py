from bridgeClass import Bridge

#Nel file main abbiamo la partenza del nostro progetto.
#Importo la classe Bridge che rappresenta il core dell'applicazione e vado a settare le variabili
#identificative di ogni dispositivo Arduino, infatti ogni dispositivo avrà un utente diverso che 
#sarà settato da questo file.
#Inoltre impostiamo anche un valore di soglia alcolica (treshold) che verosimilmente è lo stesso impostato
#sul dispositivo arduino.


if __name__ == '__main__':
        
    serial_port ="COM3"
    username="Tizio Caio"

    br = Bridge()

    #Il while in questo caso viene utilizzato per l'esecuzione "infinita" dell'applicazione
    #in questo modo ad ogni lettura del valore il ciclo non viene mai arrestato.

    while(True):
        br.start_read(serial_port,alcool_treshold,username,ride_id)
