<?php
$jsonData = file_get_contents('sites.json');
$sites = json_decode($jsonData, true);
?>

<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sites :: Status</title>

    <style>
        html,
        body {
            font-size: 13px;
        }

        a {
            text-decoration: none;
            color: #337ab7;

        }

        a:hover {
            text-decoration: underline;
        }


        table {
            border-collapse: collapse;
            width: 100%;
        }

        table,
        th,
        td {
            border: 1px solid #ddd;
            padding: 8px;
        }

        table td.icon {
            justify-items: center;
        }

        th {
            background-color: #f2f2f2;
            text-align: left;
        }

        tr:nth-child(even) {
            background-color: #f9f9f9;
        }

        tr:hover {
            background-color: #ddd;
        }

        table {
            font-family: Arial, sans-serif;
            margin: 20px 0;
        }


        .ball {
            width: 16px;
            height: 16px;
            background: #CCC;
            border-radius: 50%;
        }

        [data-status=waiting] .ball {
            background-color: rgba(255, 204, 0, 0.44);
        }

        [data-status=pending] .ball {
            background-color: #ffca00;
        }

        [data-status=success] .ball {
            background-color: rgb(0, 216, 11);
        }

        [data-status=error] .ball {
            background-color: rgb(240, 6, 6);
        }
    </style>
</head>

<body>
    <table>
        <thead>
            <th></th>
            <th>Site</th>
            <th>Status</th>
            <th>Validação</th>
        </thead>
        <tbody>
            <?php
            foreach ($sites as $key => $site) {
                echo "<tr data-status='waiting' data-indx='$key'>";
                echo "<td class='icon'><div class='ball'></div></td>";
                echo "<td class='url'><a href=" . $site['url'] . " target='_blank'>" . $site['url'] . "</a></td>";
                echo "<td class='status'>⏳ aguardando...</td>";
                echo "<td class='validate'></td>";
                echo "</tr>";
            }
            ?>
        </tbody>
    </table>

    <script>
        const rows = document.querySelectorAll('tbody tr');
        rows.forEach(row => {
            const indx = row.dataset.indx;
            (async () => {
                row.dataset.status = 'pending';
                const response = await fetch(`check-site.php?indx=${indx}`);
                const data = await response.json();
                row.dataset.status = data.status;
                row.querySelector('td.status').innerHTML = data.message;
                row.querySelector('td.validate').innerHTML = `${data.validate_check??''} ${data.validate??''}`;
            })();
        });
    </script>
</body>

</html>