import org.sosy_lab.sv_benchmarks.Verifier;

public class Main {

    public static void main(String[] args) {
        String a1 = Verifier.nondetString();
        String a2 = Verifier.nondetString();
        test(a1, a2);
    }

    public static void test(String var_1, String var_2) {
        String var_3 = var_1.concat(var_2);
        if (var_3.equals("HelloWorld")) {
            System.out.println(var_3);
        }
    }
}
