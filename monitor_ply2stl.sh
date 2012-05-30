for i in $(find  $1 -name "*.ply")
do
	filename=$(basename $i)
	python ply2stl.py $i /tmp/${filename%.*}.stl > /dev/null &
	my_pid=$(pgrep -P $$ python)
	while [ -f /proc/$my_pid/status ]
	do 
		echo $i
		echo "rss: `ps -p $my_pid -o rss=`" >> incore/mem_stl2ply_${filename%.*}.out
		sleep $2
	done
done
