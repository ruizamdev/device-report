@echo off
:: DATAGATH V 3.0
:: 
:: SCRIPT RECOPILACIÓN DE INFORMACIóN 
:: Creado por ArtmannMX
:: www.techtoolsbyartmannmx.blogspot.com
:: 10/06/2019
::
:: Configuración de la Ventana
title PC Soluciones - Servicio Tecnico
color 0a
mode con cols=80 lines=30
::
:: 
:: Cabecera
set cab0=--------------------------------------------------------------------
set cab1=                              DATAGATH  						   
set cab2=       Script Para Recopilacion de Informacion del Sistema      
set cab3=                            Version 3.0                                              
set cab4=--------------------------------------------------------------------
::______________________________________________________________________________________>
:: INICIO
::--------
::cab
echo.
echo %cab0%
echo %cab1%
echo %cab2%
echo %cab3%
echo %cab4%
echo.
echo.
::
::
:: ------------------------------------------------------------------------
:: En esta parte agregaré un generador de frases celebres de mi preferencia
:: ------------------------------------------------------------------------
::
:::
::Letra del dispositvo en el que esta este script y las utilerias
:lett
echo Escribe la Letra de la unidad en la que esta guardado este script
set/p letter=Letra=
if exist "%letter%:\data_gath3.0.cmd" (ECHO. && echo CORRECTO!) else (ECHO. && echo la letra es incorrecta && ECHO. && goto :lett)
::
:: ocultando resources
attrib +h %letter%:\resources /D /S
:: creando directorio de equipo
set userd=%COMPUTERNAME%_%USERNAME%
cls
::
::______________________________________________________________________________________>
:: VERIFICA BASE DE DATOS (SQLITE)
:: -------------------------------
::cab
echo.
echo %cab0%
echo %cab1%
echo %cab2%
echo %cab3%
echo %cab4%
echo.
echo.
%letter%:
ECHO VERIFICANDO SI EXISTE UNA BASE DE DATOS...
ECHO. 
if exist %letter%:\resources\sqlite\clientes.sqlite3 (
	echo -----VERIFICADO: && ECHO. && echo ¡YA EXISTE LA BASE DE DATOS! && echo. && pause && goto continuar 
	) else (
	goto cdb
	)
:cdb
echo -----VERIFICADO:
echo. 
echo No existe la base de datos,
echo.
ECHO CREANDO LA BASE DE DATOS
echo.
cd %letter%:\resources\sqlite
sqlite3.exe clientes.sqlite3 < schema.sql
echo ¡SE HA CREADO LA BASE DE DATOS!
ECHO.
pause
::
:: 
:continuar
cls
::______________________________________________________________________________________>
:: MUESTRA BASE DE DATOS
:: ---------------------
::cab
:initdb
echo.
echo %cab0%
echo %cab1%
echo %cab2%
echo %cab3%
echo %cab4%
echo.
echo.
echo --------------
echo base de datos:
echo --------------
echo.
echo.
%letter%:
cd %letter%:\resources\sqlite
sqlite3.exe < show_db.sql
echo.
echo.
echo En la lista de arriba aparecen los nombres de clientes 
echo de reportes anteriores, si es la primera vez que se 
echo ejecuta este script la lista estara vacia
echo.
echo Elije una opcion.
echo.
echo Ya existe el cliente? [S]i [N]o
echo.
echo Para borrar un cliente presiona [b]
set/p opc= opcion: 
if %opc% equ S set/p idc=Ingresa el Id de cliente= && goto rec_nom
if %opc% equ s set/p idc=Ingresa el Id de cliente= && goto rec_nom
if %opc% equ N echo Ingresa el Nombre del cliente: && set/p nmc= -- && echo Ingresa el/los Apellido/s del cliente: && set/p apc= -- && goto cre_nom
if %opc% equ n echo Ingresa el Nombre del cliente: && set/p nmc= -- && echo Ingresa el/los Apellido/s del cliente: && set/p apc= -- && goto cre_nom
if %opc% equ B cls && goto delete
if %opc% equ b cls && goto delete
if %opc% neq S goto :continuar
if %opc% neq s goto :continuar
if %opc% neq N goto :continuar
if %opc% neq n goto :continuar
if %opc% neq B goto :continuar
if %opc% neq b goto :continuar
pause
echo.
:cre_nom
%letter%:
if exist %letter%:\resources\sqlite\cre_nom_temp.sql (del %letter%:\resources\sqlite\cre_nom_temp.sql)
echo .open clientes.sqlite3 > %letter%:\resources\sqlite\cre_nom_temp.sql
echo INSERT INTO clientes (Nombre, Apellido) >> %letter%:\resources\sqlite\cre_nom_temp.sql
echo VALUES ('%nmc%', '%apc%'); >> %letter%:\resources\sqlite\cre_nom_temp.sql
%letter%:
cd %letter%:\resources\sqlite\
sqlite3.exe < cre_nom_temp.sql
cls
::______________________________________________________________________________________>
:: MUESTRA BASE DE DATOS (cont.)
:: -----------------------------
::cab
cls
echo.
echo %cab0%
echo %cab1%
echo %cab2%
echo %cab3%
echo %cab4%
echo.
echo. 
sqlite3.exe < show_db.sql
echo.
echo Se ha agregado el cliente a la base de datos.
echo.
pause
goto continuar2
:rec_nom
%letter%:
if exist %letter%:\resources\sqlite\rec_nom_temp.sql (del %letter%:\resources\sqlite\rec_nom_temp.sql)
cd %letter%:\resources\sqlite
echo .open clientes.sqlite3 > %letter%:\resources\sqlite\rec_nom_temp.sql
echo .output nombre.txt >> %letter%:\resources\sqlite\rec_nom_temp.sql
echo SELECT nombre FROM clientes WHERE id_cliente = %idc%; >> %letter%:\resources\sqlite\rec_nom_temp.sql
echo .open clientes.sqlite3 >> %letter%:\resources\sqlite\rec_nom_temp.sql
echo .output apellido.txt >> %letter%:\resources\sqlite\rec_nom_temp.sql
echo SELECT apellido FROM clientes WHERE id_cliente = %idc%; >> %letter%:\resources\sqlite\rec_nom_temp.sql
sqlite3.exe < rec_nom_temp.sql
%letter%:
cd "%letter%:\resources\sqlite"
for /f %%i in (nombre.txt) do set nmc=%%i
for /f %%i in (apellido.txt) do set apc=%%i
ECHO.
ECHO SE AÑADIRA UN REPORTE DE EQUIPO AL CLIENTE %nmc% %apc%
ECHO.
>nul ping -n 5 localhost
goto continuar2
::______________________________________________________________________________________>
:: MUESTRA BASE DE DATOS (cont.)
:: -----------------------------
::cab
:delete
echo.
echo %cab0%
echo %cab1%
echo %cab2%
echo %cab3%
echo %cab4%
echo.
echo. 
%letter%:
cd %letter%:\resources\sqlite
sqlite3.exe < show_db.sql
echo.
echo Para borrar un cliente escribe el id de cliente:
set/p idd= --:
echo Realmente quieres borrar este cliente?
set/p opd= [S]i [N]o =  
: ------------------> Se asignan las variables para poder borrar los archivos si el usuario lo desea.
if exist %letter%:\resources\sqlite\del_files_temp.sql (del %letter%:\resources\sqlite\del_files_temp.sql)
cd %letter%:\resources\sqlite
echo .open clientes.sqlite3 > %letter%:\resources\sqlite\del_files_temp.sql
echo .output nombre.txt >> %letter%:\resources\sqlite\del_files_temp.sql
echo SELECT nombre FROM clientes WHERE id_cliente = %idd%; >> %letter%:\resources\sqlite\del_files_temp.sql
echo .open clientes.sqlite3 >> %letter%:\resources\sqlite\del_files_temp.sql
echo .output apellido.txt >> %letter%:\resources\sqlite\del_files_temp.sql
echo SELECT apellido FROM clientes WHERE id_cliente = %idd%; >> %letter%:\resources\sqlite\del_files_temp.sql
sqlite3.exe < del_files_temp.sql
: ------------------> 
if %opd% equ s goto :borrar
if %opd% equ S goto :borrar
if %opd% equ n cls && goto delete
if %opd% equ N cls && goto delete
if %opd% neq N cls && goto delete
if %opd% neq n cls && goto delete
if %opd% neq S cls && goto delete
if %opd% neq s cls && goto delete
:borrar
%letter%:
if exist %letter%:\resources\sqlite\del_cl_temp.sql (del %letter%:\resources\sqlite\del_cl_temp.sql)
cd %letter%:\resources\sqlite
echo .open clientes.sqlite3 > %letter%:\resources\sqlite\del_cl_temp.sql
echo DELETE FROM clientes WHERE id_cliente = %idd%; >> %letter%:\resources\sqlite\del_cl_temp.sql
sqlite3.exe < del_cl_temp.sql
echo.
echo se ha borrado el cliente.
echo.
:delf
echo Quieres borrar los archivos del cliente en la carpeta de REPORTES?
ECHO.
set/p opa= [S]i [N]o =  
if %opa% equ s goto delfiles
if %opa% equ S goto delfiles
if %opa% equ N echo Regresando al menu, espere un momento... && >nul ping -n 4 localhost && goto continuar
if %opa% equ n echo Regresando al menu, espere un momento... && >nul ping -n 4 localhost && goto continuar
if %opa% neq s goto delf
if %opa% neq S goto delf
if %opa% neq n goto delf
if %opa% neq N goto delf
:delfiles
%letter%:
cd "%letter%:\resources\sqlite"
for /f %%i in (nombre.txt) do set nmc=%%i
for /f %%i in (apellido.txt) do set apc=%%i
echo %nmc%
echo %apc%
rmdir "%letter%:\REPORTES\%nmc%_%apc%" /s
echo Se han borrado los archivos
echo.
echo Regresando al menu, espera un momento...
>nul ping -n 5 localhost
goto continuar
cls
::
::______________________________________________________________________________________>
:: Crea el folder reportes si no existe
:: ------------------------------------
::cab
:continuar2
cls
echo.
echo %cab0%
echo %cab1%
echo %cab2%
echo %cab3%
echo %cab4%
echo.
echo. 
echo VERIFICANDO CARPETA DE REPORTES...
echo.
if exist %letter%:\REPORTES\ (
	echo -----VERIFICADO...
	echo.
	ECHO. ¡YA EXISTE EL FOLDER REPORTES!
	) else (md %letter%\REPORTES\
				echo -----VERIFICADO...
				echo.
				echo se ha creado el folder REPORTES!
					)
>nul ping -n 5 localhost
cls
::
::______________________________________________________________________________________>
:: Crea el folder de usuario si no existe
::cab
echo.
echo %cab0%
echo %cab1%
echo %cab2%
echo %cab3%
echo %cab4%
echo.
echo.
ECHO Creando el folder del Cliente en %letter%:\REPORTES\%nmc%_%apc%\
echo.
if exist %letter%:\REPORTES\%nmc%_%apc%\ (
	echo.
	echo ya existe el folder %nmc%_%apc%, proseguiremos...
	echo.
	) else (md %letter%:\REPORTES\%nmc%_%apc%)
echo listo!
>nul ping -n 5 localhost
cls
::
::
::______________________________________________________________________________________>
:: Crea el folder de equipo si no existe
::cab
echo.
echo %cab0%
echo %cab1%
echo %cab2%
echo %cab3%
echo %cab4%
echo.
echo.
echo Creando folder de la computadora en %letter%:\REPORTES\%nmc%_%apc%\%userd%\
echo.
if exist "%letter%:\REPORTES\%nmc%_%apc%\%userd%\" (
	echo.
	echo ya existe el folder %userd%, proseguiremos...
	echo.
	) else (md "%letter%:\REPORTES\%nmc%_%apc%\%userd%\" & echo listo!)
>nul ping -n 5 localhost
cls
::
::______________________________________________________________________________________>
:: Crea carpeta SISTEMA si no existe
::cab
echo.
echo %cab0%
echo %cab1%
echo %cab2%
echo %cab3%
echo %cab4%
echo.
echo.
echo Creando folder SISTEMA en %letter%:\REPORTES\%nmc%_%apc%\%userd%\SISTEMA\
echo.
if exist "%letter%:\REPORTES\%nmc%_%apc%\%userd%\SISTEMA\" (
	echo.
	echo ya existe el folder SISTEMA, proseguiremos...
	echo.
	) else (md "%letter%:\REPORTES\%nmc%_%apc%\%userd%\SISTEMA\" & echo Listo!)
>nul ping -n 5 localhost
cls
::
::______________________________________________________________________________________>
:: aida
::cab
echo.
echo %cab0%
echo %cab1%
echo %cab2%
echo %cab3%
echo %cab4%
echo.
echo.
:reportall
echo Si quieres generar solo el reporte de AIDA64 ENGINEER EDITION presiona [S] si no presiona [N]
set/p opra= -- :
if %opra% equ s goto aida_si
if %opra% equ S goto aida_si
if %opra% equ n goto allrep
if %opra% equ N goto allrep
if %opra% neq s goto reportall
if %opra% neq S goto reportall
if %opra% neq n goto reportall
if %opra% neq N goto reportall
::______________________________________________________________________________________>
:: Crea carpeta de RED si no existe
::cab
:allrep
cls
echo.
echo %cab0%
echo %cab1%
echo %cab2%
echo %cab3%
echo %cab4%
echo.
echo.
echo Creando folder RED en %letter%:\REPORTES\%nmc%_%apc%\%userd%\RED\
echo.
if exist "%letter%:\REPORTES\%nmc%_%apc%\%userd%\RED\" (
	echo.
	echo ya existe el folder NETINFO, proseguiremos...
	echo.
	) else (md "%letter%:\REPORTES\%nmc%_%apc%\%userd%\RED\" & echo listo!)
>nul ping -n 5 localhost
cls
::
::______________________________________________________________________________________>
:: Crea carpeta de redesWIFI si no existe
::cab
echo.
echo %cab0%
echo %cab1%
echo %cab2%
echo %cab3%
echo %cab4%
echo.
echo.
echo. Creando folder redesWIFI en %letter%:\REPORTES\%nmc%_%apc%\%userd%\RED\redesWIFI\
echo.
if exist "%letter%:\REPORTES\%nmc%_%apc%\%userd%\RED\redesWIFI\" (
	echo.
	echo Ya existe el folder WiFiData, proseguiremos...
	echo.
	) else (md "%letter%:\REPORTES\%nmc%_%apc%\%userd%\RED\redesWIFI\" & echo listo!)
>nul ping -n 5 localhost
cls
::
::______________________________________________________________________________________>
:: IPCONFIG
::cab
echo.
echo %cab0%
echo %cab1%
echo %cab2%
echo %cab3%
echo %cab4%
echo.
echo.
echo Volcando salida del comando IPCONFIG al archivo %letter%:\REPORTES\%nmc%_%apc%\%userd%\RED\IPCONFIG.txt
echo.
ipconfig > "%letter%:\REPORTES\%nmc%_%apc%\%userd%\RED\IPCONFIG.txt"
echo listo!
>nul ping -n 5 localhost
cls
::
::______________________________________________________________________________________>
:: Configuracion del archivo del perfil de red
::cab
echo.
echo %cab0%
echo %cab1%
echo %cab2%
echo %cab3%
echo %cab4%
echo.
echo.
echo OBTENIENDO INFORMACION DE RED INALAMBRICA...
echo.
set wififile="%letter%:\REPORTES\%nmc%_%apc%\%userd%\RED\conexionWIFI_%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%%time:~6,2%.txt"
echo.
echo.
echo Copiando informacion de netsh wlan...
echo espere un momento...
echo.
::
::
:: Todo este bloque se escribirá en el archivo
	echo. > %wififile%
	echo --------------------------------------------- >> %wififile%
	echo Informacion de conexiones de red inalambricas >> %wififile%
	echo de la computadora %COMPUTERNAME% y el usuario >> %wififile%
	echo               %USERNAME% >> %wififile%
	echo Ruta de usuario: %USERPROFILE% >> %wififile%
	echo --------------------------------------------- >> %wififile%
	echo. >> %wififile%
	echo. >> %wififile%
	netsh wlan show profiles >> %wififile%
	echo. >> %wififile%
	netsh wlan show interfaces >> %wififile%
	echo. >> %wififile%
	netsh wlan show drivers >> %wififile%
	echo. >> %wififile%
	netsh wlan show wirelesscapabilities >> %wififile%
	echo. >> %wififile%
:: fin del bloque
>nul ping -n 5 localhost
cls
::
::
::______________________________________________________________________________________>
:: Aqui exportamos todos los perfiles de conexion inalámbricas 
:: existentes.
::cab
echo.
echo %cab0%
echo %cab1%
echo %cab2%
echo %cab3%
echo %cab4%
echo.
echo.
ECHO Exportando todos los perfiles de conexion inalambrica que existen en el dispositivo...
netsh wlan export profile key=clear folder="%letter%:\REPORTES\%nmc%_%apc%\%userd%\RED\redesWIFI"
ECHO.
echo.
echo listo!
>nul ping -n 5 localhost
cls
::
::
::______________________________________________________________________________________>
:: DMIDECODE
::cab
echo.
echo %cab0%
echo %cab1%
echo %cab2%
echo %cab3%
echo %cab4%
echo.
echo.
echo DECODIFICANDO DMI DEL EQUIPO Y VOLCANDO SALIDA DEL COMANDO SYSTEMINFO...
echO.
%letter%:\resources\dmidecode.exe > "%letter%:\REPORTES\%nmc%_%apc%\%userd%\SISTEMA\dmidecode.txt"
systeminfo > "%letter%:\REPORTES\%nmc%_%apc%\%userd%\SISTEMA\sysinfo.txt"
echo. 
echo.
echo.
echo Listo!
ECHO.
echo.
echo.
>nul ping -n 5 localhost
cls
::
::
::______________________________________________________________________________________>
::
::
:: REPORTE AIDA64 ENGINEER
::
::
::cab
:aida64
echo.
echo %cab0%
echo %cab1%
echo %cab2%
echo %cab3%
echo %cab4%
echo.
echo.
echo Quieres generar un reporte con AIDA64 ENGINEER EDITION?
ECHO Tardara varios minutos en competarse.
set/p opc0= [S]i [N]o= 
if %opc0% equ S goto aida_si
if %opc0% equ s goto aida_si
if %opc0% equ N goto endscript
if %opc0% equ n goto endscript
if %opc0% neq S goto aida64
if %opc0% neq s goto aida64
if %opc0% neq N goto aida64
if %opc0% neq n goto aida64
echo.
::______________________________________________________________________________________>
::
::cab
:aida_si
cls
echo.
echo %cab0%
echo %cab1%
echo %cab2%
echo %cab3%
echo %cab4%
echo.
echo.
echo Generando reporte con herramienta AIDA64 ENGINEER EDITION
echo.
ECHO.
ECHO ESPERE UN MOMENTO HASTA QUE TERMINE EL PROCESO...
echo.
echo podra ver el progreso en la barra de tareas, 
echo en la bandeja de notificacion, aparecera el 
echo icono del programa y el conteo de reportes...
%letter%:\resources\AIDA64\aida64.exe /R "%letter%:\REPORTES\%nmc%_%apc%\%userd%\SISTEMA\a64report_%COMPUTERNAME%" /ALL /HTML
echo.
echo.
echo.
echo Listo!
echo.
echo.
echo.
:endscript
echo [R]egresar al inicio o [S]alir?
echo.
set/p opend= --:  
if %opend% equ R cls && goto initdb
if %opend% equ r cls && goto initdb
if %opend% equ S goto salirscript
if %opend% equ s goto salirscript
if %opend% neq R goto endscript
if %opend% neq r goto endscript
if %opend% neq S goto endscript
if %opend% neq s goto endscript
:salirscript
echo Se abrira la carpeta del reporte despues de cerrar esta ventana
echo.
>nul ping -n 3 localhost
cd "%letter%:\REPORTES\%nmc%_%apc%\%userd%\"
start.
if exist "%letter%:\REPORTES\%nmc%_%apc%\%userd%\SISTEMA\a64report_%COMPUTERNAME%.htm" start "%letter%:\REPORTES\%nmc%_%apc%\%userd%\SISTEMA\a64report_%COMPUTERNAME%.htm"
:EOF

