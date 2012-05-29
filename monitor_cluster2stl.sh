for i in $(find $1  -name "*.ply")
do
	filename=$(basename $i)
	python clusters2stl.py $i /tmp/${filename%.*}.stl > /dev/null &
	my_pid=$(pgrep -P $$ python)
	while [ -f /proc/$my_pid/status ]
	do 
		echo $i
		echo "RSS: `ps -p $my_pid -o rss=`"  >> outofcore/mem_${filename%.*}.out
		sleep 1
	done
done
