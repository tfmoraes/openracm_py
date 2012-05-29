for i in $(find /home/thiago/Meshes/Resultados/Sort/10_05_2012/  -name "*.ply")
do
	filename=$(basename $i)
	python ply2stl.py $i /tmp/${filename%.*}.stl > /dev/null &
	my_pid=$(pgrep -P $$ python)
	while [ -f /proc/$my_pid/status ]
	do 
		echo $i
		echo "rss: `ps -p $my_pid -o rss=`" >> mem_stl2ply_${filename%.*}.out
		sleep 1
	done
done
