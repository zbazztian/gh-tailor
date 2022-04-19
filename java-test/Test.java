import java.io.*;

public class Test{
	public static void main(String[] args) throws IOException{
		File f = new File(args[0]);
		String line = new BufferedReader(new FileReader(f)).readLine();
		System.out.println(line);
	}
}
