#!/bin/bash

# Get my email address (for notifications)
email=$(cat ~/.email)
email_from=$(cat ~/.emailfrom)

# Load environment modules
module load Python ffmpeg
nolinks=$(mktemp)
error=$(mktemp)
failures=$(mktemp)
logfile=$(mktemp)
emailbody=$(mktemp)
tmpout=$(mktemp)

function get_links() {
  echo "Getting links for ${1} ..."
  nbcdl -N -s "${2}" -o "${3}" ${4} > ${tmpout} 2>&1
  retcd=$?
  if [ ${retcd} -eq 90 ] ; then
    echo "${1}" >> ${nolinks}
    cat ${tmpout} >> ${logfile}
    echo '#################################' >> ${logfile}
  elif [ ${retcd} -gt 0 ] ; then
    echo "${1} (${retcd})" >> ${error}
    cat ${tmpout} >> ${logfile}
    echo '#################################' >> ${logfile}
  fi
}

# News programs (organized by month)
get_links 'NBC Nightly News (nbcnews.com)' 'https://www.nbcnews.com/nightly-news' '/data/vids/News Shows/Nightly News'
get_links 'NBC Nightly News (nbc.com)' 'https://www.nbc.com/nbc-nightly-news' '/data/vids/News Shows/Nightly News'
get_links 'Nightly News Kids Edition' 'https://www.nbcnews.com/nightlykids' '/data/vids/News Shows/Nightly News Kids Edition'
get_links 'TODAY' 'https://www.nbc.com/today' '/data/vids/News Shows/TODAY'

# Late Night TV (organized by quarter)
get_links 'The Tonight Show Starring Jimmy Fallon' 'https://www.nbc.com/the-tonight-show' '/data/vids/News Shows/The Tonight Show Starring Jimmy Fallon' '-q'
get_links 'Late Night with Seth Meyers' 'https://www.nbc.com/late-night-with-seth-meyers' '/data/vids/News Shows/Late Night with Seth Meyers' '-q'
get_links 'A Little Late with Lilly Singh' 'https://www.nbc.com/a-little-late-with-lilly-singh' '/data/vids/News Shows/A Little Late with Lilly Singh' '-q'

# Email me for shows where we couldn't find any links
if [ -s ${nolinks} ] ; then
  echo 'PROBLEM SHOWS:' > ${emailbody}
  cat ${nolinks} >> ${emailbody}
  echo '##################################' >> ${emailbody}
  cat ${logfile} >> ${emailbody}

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
  cat ${error} >> ${emailbody}
  echo '##################################' >> ${emailbody}
  cat ${logfile} >> ${emailbody}

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
echo ''>${logfile}
echo ''>${error}
IFS=$'\n'
for i in $(find /data/vids/News\ Shows -mindepth 0 -type d) ; do
  cd "${i}" > /dev/null
    if [ -f "url.txt" ] ; then
      echo "PROCESSING ${i} ..."
      echo "PROCESSING ${i} ..." >> ${logfile}
      nbcdl -S 24 -c -q url.txt > ${tmpout} 2>&1
      retcd=$?
      if [ ${retcd} -eq 91 ] ; then
        echo "${i}" >> ${failures}
        cat ${tmpout} >> ${logfile}
        echo '#################################' >> ${logfile}
      elif [ ${retcd} -gt 0 ] ; then
        echo "${i} (${retcd})" >> ${error}
        cat ${tmpout} >> ${logfile}
        echo '#################################' >> ${logfile}
      fi
    fi
  cd - > /dev/null
done
pwd

# Email me for directories where some videos could not be downloaded
if [ -s ${failures} ] ; then
  echo 'PROBLEM DIRECTORIES:' > ${emailbody}
  cat ${failures} >> ${emailbody}
  echo '##################################' >> ${emailbody}
  cat ${logfile} >> ${emailbody}

  w=$(wc -l ${failures}|awk '{print $1}')
  if [ ${w} -eq 1 ] ; then
    subject="[WARNING] Failures for $(sed -n 1p ${failures})"
  else
    subject="[WARNING] Failures for ${w} directories"
  fi
  echo "Some videso could not be downloaded, sending an email to ${email}..."
  mail -r ${email_from} -s "${subject}" ${email} < ${emailbody}
fi

# Email me about any other serious script errors
if [ -s ${error} ] ; then
  echo 'PROBLEM DIRECTORIES:' > ${emailbody}
  cat ${error} >> ${emailbody}
  echo '##################################' >> ${emailbody}
  cat ${logfile} >> ${emailbody}

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
cp -av ${logfile} log.txt
rm -fv ${nolinks} ${error} ${failures} ${logfile} ${emailbody} ${tmpout}
