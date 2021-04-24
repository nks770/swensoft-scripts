#!/bin/bash

# Get my email address (for notifications)
email=$(cat ~/.email)
email_from=$(cat ~/.emailfrom)

# Load environment modules
export PATH=/usr/local/bin:${PATH}
source /opt/Modules/4.1.3/init/sh
module load Python ffmpeg

# Create temporary files
nolinks=$(mktemp)
error=$(mktemp)
failures=$(mktemp)
logfile=$(mktemp)
logfile2=$(mktemp)
emailbody=$(mktemp)
tmpout=$(mktemp)
tmperr=$(mktemp)

function chomp() {
  w=$(wc -l ${1}|awk '{print $1}')
  x=$(($w+$w))
  if [ ${x} -le ${2} ] ; then
    cat ${1}
  else
    head -n ${2} ${1}
    echo '..................<snip>..................'
    tail -n ${2} ${1}
  fi
}

function get_links() {
  echo "Getting links for ${1} ..."
  nbcdl -N -s "${2}" -o "${3}" ${4} > ${tmpout} 2> ${tmperr}
  retcd=$?
  if [ ${retcd} -eq 90 ] ; then
    echo '#################################' >> ${logfile}
    echo "${1}" >> ${nolinks}
    chomp ${tmpout} 20 >> ${logfile}
    chomp ${tmperr} 20 >> ${logfile}
    echo "RETURN CODE ${retcd}" >> ${logfile}
  elif [ ${retcd} -gt 0 ] ; then
    echo '#################################' >> ${logfile2}
    #echo "${1} (${retcd})" >> ${error}
    echo "${1}" >> ${error}
    chomp ${tmpout} 20 >> ${logfile2}
    chomp ${tmperr} 20 >> ${logfile2}
    echo "RETURN CODE ${retcd}" >> ${logfile2}
  fi
}

# News programs (organized by month)
get_links 'NBC Nightly News (nbcnews.com)' 'https://www.nbcnews.com/nightly-news' '/data/vids/News Shows/Nightly News'
get_links 'NBC Nightly News (nbc.com)' 'https://www.nbc.com/nbc-nightly-news' '/data/vids/News Shows/Nightly News'
get_links 'Nightly News Kids Edition' 'https://www.nbcnews.com/nightlykids' '/data/vids/News Shows/Nightly News Kids Edition'
get_links 'TODAY' 'https://www.nbc.com/today' '/data/vids/News Shows/TODAY'

# Dateline
get_links 'Dateline' 'https://www.nbc.com/dateline' '/data/vids/News Shows/Dateline' '-Q'

# Late Night TV (organized by quarter)
get_links 'The Tonight Show Starring Jimmy Fallon' 'https://www.nbc.com/the-tonight-show' '/data/vids/News Shows/The Tonight Show Starring Jimmy Fallon' '-Q'
get_links 'Late Night with Seth Meyers' 'https://www.nbc.com/late-night-with-seth-meyers' '/data/vids/News Shows/Late Night with Seth Meyers' '-Q'
get_links 'A Little Late with Lilly Singh' 'https://www.nbc.com/a-little-late-with-lilly-singh' '/data/vids/News Shows/A Little Late with Lilly Singh' '-Q'

# Email me for shows where we couldn't find any links
if [ -s ${nolinks} ] ; then
  echo 'PROBLEM SHOWS:' > ${emailbody}
  cat ${nolinks} ${logfile} >> ${emailbody}

  w=$(wc -l ${nolinks}|awk '{print $1}')
  if [ ${w} -eq 1 ] ; then
    subject="[WARNING] No links for $(sed -n 1p ${nolinks})"
  else
    subject="[WARNING] No links for ${w} shows"
  fi
  echo "We couldn't find links for some shows, sending an email to ${email}..."
  mail -r ${email_from} -s "${subject}" ${email} < ${emailbody}
fi

# Email me about any serious script errors
if [ -s ${error} ] ; then
  echo 'PROBLEM SHOWS:' > ${emailbody}
  cat ${error} ${logfile2} >> ${emailbody}

  w=$(wc -l ${error}|awk '{print $1}')
  if [ ${w} -eq 1 ] ; then
    subject="[ERROR] Errors occurred for $(sed -n 1p ${error})"
  else
    subject="[ERROR] Errors occurred for ${w} shows"
  fi
  echo "An error occurred for some shows, sending an email to ${email}..."
  mail -r ${email_from} -s "${subject}" ${email} < ${emailbody}
fi

# Loop through directories to find url.txt files, and run them
rm -f ${error} ${logfile} ${logfile2}
IFS=$'\n'
for i in $(find /data/vids/News\ Shows -mindepth 0 -type d) ; do
  cd "${i}" > /dev/null
    if [ -f "url.txt" ] ; then
      echo "PROCESSING ${i} ..."
      nbcdl -N -S 100 -c -e -q url.txt > ${tmpout} 2> ${tmperr}
      retcd=$?
      #cp -av ${tmpout} $(date +%Y%m%d-%H%M%S)-out.log
      #cp -av ${tmperr} $(date +%Y%m%d-%H%M%S)-err.log
      if [ ${retcd} -eq 91 ] ; then
        echo "${i}" >> ${failures}
        echo '#################################' >> ${logfile}
        echo "PROCESSING ${i} ..." >> ${logfile}
        chomp ${tmpout} 20 >> ${logfile}
        chomp ${tmperr} 20 >> ${logfile}
        echo "RETURN CODE ${retcd}" >> ${logfile}
      elif [ ${retcd} -gt 0 ] ; then
        #echo "${i} (${retcd})" >> ${error}
        echo "${i}" >> ${error}
        echo '#################################' >> ${logfile2}
        echo "PROCESSING ${i} ..." >> ${logfile2}
        chomp ${tmpout} 20 >> ${logfile2}
        chomp ${tmperr} 20 >> ${logfile2}
        echo "RETURN CODE ${retcd}" >> ${logfile2}
      fi
    fi
  cd - > /dev/null
done
pwd

# Email me for directories where some videos could not be downloaded
if [ -s ${failures} ] ; then
  echo 'DIRECTORIES WITH FAILED VIDEOS:' > ${emailbody}
  cat ${failures} ${logfile} >> ${emailbody}

  w=$(wc -l ${failures}|awk '{print $1}')
  if [ ${w} -eq 1 ] ; then
    subject="[WARNING] Failures for $(sed -n 1p ${failures})"
  else
    subject="[WARNING] Failures for ${w} directories"
  fi
  echo "Some videos could not be downloaded, sending an email to ${email}..."
  mail -r ${email_from} -s "${subject}" ${email} < ${emailbody}
fi

# Email me about any other serious script errors
if [ -s ${error} ] ; then
  echo 'PROBLEM DIRECTORIES:' > ${emailbody}
  cat ${error} ${logfile2} >> ${emailbody}

  w=$(wc -l ${error}|awk '{print $1}')
  if [ ${w} -eq 1 ] ; then
    subject="[ERROR] Errors occurred for $(sed -n 1p ${error})"
  else
    subject="[ERROR] Errors occurred for ${w} directories"
  fi
  echo "Some other kind of script errors occurred, sending an email to ${email}..."
  mail -r ${email_from} -s "${subject}" ${email} < ${emailbody}
fi
# Clean up
rm -fv ${nolinks} ${error} ${failures} ${logfile} ${logfile2} ${emailbody} ${tmpout} ${tmperr}
