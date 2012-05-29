for i in $(find /home/thiago/Meshes/Resultados/Cluster/09_05_2012/ -name "*.ply")
do
	filename=$(basename $i)
	python clusters2stl.py $i /tmp/${filename%.*}.stl > /dev/null &
	my_pid=$(pgrep -P $$ python)
	while [ -f /proc/$my_pid/status ]
	do 
		echo $i
		echo "VMSize: `ps -p $my_pid -o vsize=`" >> mem_${filename%.*}.out
		sleep 1
	done
done
